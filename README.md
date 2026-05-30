# llm-structured-scraper

A two-stage pipeline that renders JavaScript-heavy pages in a headless browser, converts them to token-efficient Markdown, and uses an LLM to extract **structured data** you define with [Pydantic](https://docs.pydantic.dev/)—enforced at the API boundary via [Instructor](https://python.useinstructor.com/).

Traditional scrapers depend on fixed CSS selectors and regex. When layouts change, they break. This project sends cleaned page content to an LLM with a strict schema and system prompt, so extraction follows **meaning** rather than DOM structure. You choose the fields (URLs, titles, prices, dates, and so on); the pipeline stays the same.

## Features

- **Headless scraping** — Playwright (with stealth) loads dynamic pages; configurable `wait_until` for sites that never reach `networkidle`.
- **HTML → Markdown** — Strips scripts, styles, navigation, and other noise before conversion to cut tokens while keeping headings, lists, and links.
- **Token-aware chunking** — Splits long pages at line boundaries with `tiktoken` so chunks stay within model limits.
- **Schema-driven extraction** — Define a Pydantic model and prompt in `scripts/main.py`; Instructor validates every LLM response.
- **CSV export** — Aggregated results are written to `data/data.csv` for spreadsheets or downstream scripts.
- **Cloud or local LLMs** — Groq (remote) or Ollama (local) via a single `is_local` flag.
- **Usage reporting** — Per-chunk prompt, completion, and total token counts for cost and debugging.

## Quick start

**1. Clone**

```bash
git clone https://github.com/sadmanhsakib/llm_structured_scraper.git
cd llm_structured_scraper
```

**2. Install dependencies**

```bash
uv sync
```

**3. Configure environment**

```bash
copy example.env .env    # Windows
cp example.env .env      # macOS / Linux
```

| Variable | Description |
|----------|-------------|
| `API_KEY` | Groq API key (remote only) |
| `SITE_URL` | Page to scrape |
| `LOCAL_MODEL_NAME` | Ollama model (e.g. `llama3.2`) |
| `REMOTE_MODEL_NAME` | Groq model (e.g. `llama-3.3-70b-versatile`) |

**4. Run**

Customize the extraction schema and prompt in `scripts/main.py` (see [Customization](#customization)), then run from the **repository root**:

```bash
uv run python main.py
```

Output: `data/webpage.md` (intermediate) and `data/data.csv` (final).

## How it works

```
SITE_URL (.env)
      │
      ▼
┌─────────────┐     data/webpage.md     ┌─────────────┐     data/data.csv
│  scraper.py │ ──────────────────────► │  parser.py  │ ─────────────────►
│  Playwright │                         │  chunk →    │
│  + Markdown │                         │  LLM → CSV  │
└─────────────┘                         └─────────────┘
      ▲                                         ▲
      │                                         │
 scripts/main.py  (Schema, SYSTEM_PROMPT, is_local)
```

1. **Scrape** — `fetch_page()` loads the URL and returns HTML. `export_as_markdown()` strips non-content tags, converts to Markdown, and saves `data/webpage.md`.
2. **Extract** — `extract_data_from_markdown()` chunks the Markdown, sends each chunk to the LLM with your system prompt, merges validated records, and writes `data/data.csv`.

Temperature is `0.0` to reduce hallucinations. Responses must match `SchemaCollection` (a list of your `Schema` model).

## Customization

The pipeline is generic: you control **what** is extracted by editing `scripts/main.py`.

**1. Pydantic schema** — fields must match what you ask the model to return:

```python
class Schema(BaseModel):
    title: str
    duration: str
    url: HttpUrl
```

`parser.py` wraps these in `SchemaCollection` (`collections: List[main.Schema]`). After you change `Schema`, update `SYSTEM_PROMPT` so the model knows which fields to fill.

**2. System prompt** — keep instructions strict (JSON only, no markdown fences, no prose):

```python
SYSTEM_PROMPT = """
You are a data extraction assistant.
Respond ONLY with a valid JSON object. No explanation, no markdown fences.
Extract only the information related to the VIDEO.
For example, video title, video duration, video url.
"""
```

**3. LLM backend** — pass `is_local` to `extract_data_from_markdown()`:

```python
parser.extract_data_from_markdown(
    md_path=md_path,
    SYSTEM_PROMPT=SYSTEM_PROMPT,
    is_local=False,   # True → Ollama, False → Groq
)
```

**4. Page load behavior** — adjust `wait_until` when calling `fetch_page()` (`"load"`, `"domcontentloaded"`, or `"networkidle"`).

**5. Chunk size** — defaults are 1,500 tokens (local) and 6,000 (remote). Override by passing a different `max_tokens` to `chunk_text()` in `parser.py` if needed.

## Project structure

```
llm-data-extractor/
├── scripts/
│   ├── main.py       # Entry point: schema, prompt, orchestration
│   ├── parser.py     # Chunking, LLM calls, CSV export
│   ├── scraper.py    # Playwright fetch + HTML → Markdown
│   └── test.py       # Optional utilities over data/data.csv
├── data/             # Generated at runtime (gitignored)
│   ├── webpage.md
│   └── data.csv
├── example.env
├── requirements.txt
└── README.md
```

Run commands from the **repository root** so paths like `data/webpage.md` resolve correctly.

## Prerequisites

- Python 3.10+
- Playwright Chromium (`playwright install chromium`)
- **Groq**: API key and model name in `.env`
- **Ollama** (optional): [Ollama](https://ollama.com/) running locally with your model pulled

## Usage

### Full pipeline

```bash
python scripts/main.py
```

### Run stages separately

**Scrape only** — from the repository root:

```python
import sys, asyncio
sys.path.insert(0, "scripts")
from scraper import fetch_page, export_as_markdown

html = asyncio.run(fetch_page("https://example.com", wait_until="load"))
export_as_markdown(html)
```

**Extract only** — requires `data/webpage.md` and the same `Schema` / prompt as in `main.py`:

```python
import main as app
from parser import extract_data_from_markdown

extract_data_from_markdown(
    md_path="../data/webpage.md",  # relative to scripts/ if cwd is scripts/
    SYSTEM_PROMPT=app.SYSTEM_PROMPT,
    is_local=False,
)
```

When using extract-only, run from the **repository root** and pass `md_path="data/webpage.md"` so paths match the full pipeline.

## LLM backends

| | Groq (remote) | Ollama (local) |
|---|---------------|----------------|
| Speed | Fast | Hardware-dependent |
| Privacy | Data sent to Groq | Stays on your machine |
| Cost | API usage | Free (your compute) |
| Setup | `API_KEY` + `REMOTE_MODEL_NAME` | Ollama + `LOCAL_MODEL_NAME` |
| Default chunk size | 6,000 tokens | 1,500 tokens |

Local chunks use a smaller default to fit typical 7B–14B context windows.

## Token budget and chunking

Chunk sizes use `tiktoken` with the `cl100k_base` encoding—an approximation for non-OpenAI models, but sufficient to avoid context overflows. Each chunk logs its estimated token count. If extraction misses items on dense pages, try a larger `max_tokens` or tighten the HTML strip list in `export_as_markdown()`.

## Tech stack

| Library | Role |
|---------|------|
| [Playwright](https://playwright.dev/python/) | Headless browser |
| [playwright-stealth](https://github.com/AtuboDad/playwright_stealth) | Reduced bot detection |
| [markdownify](https://github.com/matthewwithanm/python-markdownify) | HTML → Markdown |
| [Instructor](https://python.useinstructor.com/) | Structured LLM output |
| [Pydantic](https://docs.pydantic.dev/) | Schemas and validation |
| [Groq](https://groq.com/) / [Ollama](https://ollama.com/) | Inference backends |
| [tiktoken](https://github.com/openai/tiktoken) | Token counting |
| [pandas](https://pandas.pydata.org/) | CSV export |

Pinned versions are in `requirements.txt`.

## Troubleshooting

| Issue | What to try |
|-------|-------------|
| `Input file not found: data/webpage.md` | Run the scraper first, or run from the repo root. |
| `Model name not configured` | Set `LOCAL_MODEL_NAME` or `REMOTE_MODEL_NAME` + `API_KEY` in `.env`. |
| Playwright browser missing | `playwright install chromium` in your venv. |
| Empty CSV / no rows | Inspect `data/webpage.md`; widen the prompt or chunk size; confirm the page contains the data you expect. |
| Ollama connection refused | Start Ollama (`ollama serve`) and `ollama pull <model>`. |
| Timeout on `page.goto()` | Use `wait_until="load"` or `"domcontentloaded"` instead of `"networkidle"`. |
| Invalid JSON / validation errors | Tighten `SYSTEM_PROMPT`; consider `max_retries=3` in `generate_output()` for production. |

## License

Provided as-is for educational and personal use. No warranty is expressed or implied.
