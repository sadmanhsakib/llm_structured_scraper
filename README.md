# llm-structured-scraper

A production-ready web scraping pipeline that combines advanced stealth techniques with LLM-powered structured data extraction. This tool loads JavaScript-heavy pages using a headless browser with anti-detection features, converts them to token-efficient Markdown, and uses an LLM to extract **structured data** based on schemas you define with [Pydantic](https://docs.pydantic.dev/)—enforced at the API boundary via [Instructor](https://python.useinstructor.com/).

Traditional scrapers break when layouts change because they rely on fixed CSS selectors and regex. This project takes a different approach: it sends cleaned page content to an LLM with your custom schema and system prompt, so extraction follows **semantic meaning** rather than DOM structure. You define the fields (URLs, titles, prices, dates, etc.) using Pydantic models, and the pipeline handles the rest.

## Features

### Stealth & Anti-Detection

- **Advanced stealth browser** — Custom `StealthPlaywrightScraper` class with rotating user agents, screen resolutions, and timezones
- **Anti-detection measures** — Removes webdriver flags, injects Chrome runtime objects, and randomizes browser fingerprints
- **Playwright stealth plugin** — Integrated `playwright-stealth` for maximum stealth capabilities
- **Proxy support** — Built-in proxy configuration for IP rotation and geo-targeting
- **Concurrent scraping** — Semaphore-based concurrency control for scalable multi-page extraction
- **Retry logic** — Automatic retries with exponential backoff for resilient scraping

### Data Processing

- **HTML → Markdown conversion** — Strips scripts, styles, navigation, and other noise before conversion to reduce token usage
- **Token-aware chunking** — Intelligently splits long pages at line boundaries using `tiktoken` to stay within model limits
- **Schema-driven extraction** — Define Pydantic models in `scripts/main.py`; Instructor validates every LLM response
- **CSV export** — Aggregated results written to `data/data.csv` for easy analysis
- **Flexible wait conditions** — Support for `load`, `domcontentloaded`, `networkidle`, and custom selectors

### LLM Integration

- **Cloud or local LLMs** — Groq (remote) or Ollama (local) via a single `is_local` flag
- **Structured output** — Guaranteed valid JSON conforming to your Pydantic schema
- **Usage reporting** — Per-chunk prompt, completion, and total token counts for cost tracking
- **Zero-temperature extraction** — Minimizes hallucinations for consistent, reliable results

## Quick start

**1. Clone**

```bash
git clone https://github.com/sadmanhsakib/llm_structured_scraper.git
cd llm_structured_scraper
```

**2. Install dependencies**

This project uses [uv](https://docs.astral.sh/uv/) for fast, reliable dependency management:

```bash
uv sync
```

Playwright browser installation (required):

```bash
uv run playwright install chromium
```

**3. Configure environment**

```bash
copy example.env .env    # Windows
cp example.env .env      # macOS / Linux
```

Edit `.env` with your settings:

| Variable            | Description                | Example                   |
| ------------------- | -------------------------- | ------------------------- |
| `API_KEY`           | Groq API key (remote only) | `gsk_...`                 |
| `SITE_URL`          | Page to scrape             | `https://example.com`     |
| `LOCAL_MODEL_NAME`  | Ollama model (local only)  | `llama3.2`                |
| `REMOTE_MODEL_NAME` | Groq model (remote only)   | `llama-3.3-70b-versatile` |

**4. Customize extraction schema**

Edit `scripts/config.py` to define what data you want to extract:

```python
class Schema(BaseModel):
    """Schema for a single extracted data point."""
    title: str
    url: HttpUrl
    price: Optional[str] = None
```

Update the `SYSTEM_PROMPT` to match your schema:

```python
SYSTEM_PROMPT = """
You are a data extraction assistant.
Respond ONLY with a valid JSON object. No explanation, no markdown fences.
Extract product information: title, url, and price (if available).
"""
```

**5. Run**

From the **repository root**:

```bash
uv run python scripts/main.py
```

Output files:
- `data/webpage.md` — Cleaned markdown of the scraped page
- `data/data.csv` — Extracted structured data

## How it works

```
SITE_URL (.env)
      │
      ▼
┌───────────────────┐     data/webpage.md     ┌─────────────┐     data/data.csv
│   scraper.py      │ ──────────────────────► │  parser.py  │ ─────────────────►
│  StealthPlaywright│                         │  chunk →    │
│  + Anti-Detection │                         │  LLM → CSV  │
│  + Markdown       │                         │             │
└───────────────────┘                         └─────────────┘
      ▲                                               ▲
      │                                               │
           scripts/main.py (Schema, SYSTEM_PROMPT, orchestration)
```

### Pipeline stages

1. **Fetch** — `StealthPlaywrightScraper` launches a headless Chromium instance with randomized fingerprints (user agent, screen resolution, timezone). It applies stealth techniques to bypass bot detection and waits for the specified page load condition (`networkidle` by default).

2. **Convert** — `export_as_markdown()` strips non-content HTML tags (scripts, styles, navigation, ads) and converts the remaining content to Markdown, preserving structure while dramatically reducing token count.

3. **Chunk** — `chunk_text()` uses `tiktoken` to split the Markdown into chunks that fit within the model's context window (1,500 tokens for local, 6,000 for remote), splitting at line boundaries to preserve context.

4. **Extract** — For each chunk, `generate_output()` sends the content to the LLM with your system prompt and Pydantic schema. Instructor enforces structured output, ensuring every response is valid JSON matching your schema.

5. **Export** — All extracted records are aggregated into a single `SchemaCollection` and written to `data/data.csv` using pandas.

Temperature is set to `0.0` to minimize hallucinations and ensure consistent, factual extraction.

## Customization

The pipeline is designed to be generic—you control **what** gets extracted by editing `scripts/main.py`.

### 1. Define your Pydantic schema

Fields must match the data you want the LLM to extract:

```python
from pydantic import BaseModel, HttpUrl
from typing import Optional

class Schema(BaseModel):
    """Schema for a single extracted data point."""
    title: str
    duration: str
    url: HttpUrl
    author: Optional[str] = None
```

The parser wraps your schema in `SchemaCollection` (a list of `Schema` objects) to handle multiple records per chunk.

### 2. Write a system prompt

Keep instructions strict and focused. The LLM should return **only** JSON—no markdown fences, no explanations:

```python
SYSTEM_PROMPT = """
You are a data extraction assistant.
Respond ONLY with a valid JSON object. No explanation, no markdown fences.
Extract video metadata from the provided content:
- title: video title
- duration: video length
- url: video URL
- author: channel or creator name (if available)
"""
```

### 3. Configure the scraper

In the `main()` function, adjust scraping parameters as needed:

```python
async def main():
    html_content = await scraper.fetch_page(
        url=SITE_URL,
        wait_until="networkidle",  # Options: "load", "domcontentloaded", "networkidle"
        timeout=30000,             # 30 seconds
        wait_for_selector=".content",  # Optional: wait for specific element
        wait_for_timeout=2000,     # Optional: additional wait in ms
    )
    output_path = scraper.export_as_markdown(html_content)

    parser.extract_data_from_markdown(
        md_path=output_path,
        SYSTEM_PROMPT=SYSTEM_PROMPT,
        is_local=False,  # True → Ollama, False → Groq
    )
```

### 4. Advanced scraping options

For more control, use the `StealthPlaywrightScraper` class directly:

```python
from scraper import StealthPlaywrightScraper

async def advanced_scraping():
    async with StealthPlaywrightScraper(
        headless=True,
        max_concurrent_browsers=3,
        proxy={"server": "http://proxy.example.com:8080"},
        use_stealth=True,
    ) as scraper:
        html = await scraper.fetch_page(
            url="https://example.com",
            wait_until="networkidle",
            retry_count=3,
            delay_between_retries=2.0,
        )
        # Process html...
```

### 5. Adjust chunk size

Default chunk sizes are 1,500 tokens (local) and 6,000 tokens (remote). To override:

```python
# In parser.py, modify the chunk_text call:
chunks = chunk_text(markdown_content, max_tokens=4000)
```

## Project structure

```
llm-structured-scraper/
├── scripts/
│   ├── main.py          # Entry point: schema, system prompt, orchestration
│   ├── scraper.py       # StealthPlaywrightScraper class + HTML → Markdown
│   ├── parser.py        # Token-aware chunking, LLM calls, CSV export
│   └── test.py          # Optional utilities for data/data.csv analysis
├── data/                # Generated at runtime (gitignored)
│   ├── webpage.md       # Intermediate markdown output
│   └── data.csv         # Final structured data export
├── .venv/               # Virtual environment (uv managed)
├── pyproject.toml       # Project metadata and dependencies
├── uv.lock              # Locked dependency versions
├── example.env          # Environment variable template
├── .env                 # Your actual configuration (gitignored)
├── .python-version      # Python version specification
└── README.md            # This file
```

**Important:** Always run commands from the **repository root** so relative paths like `data/webpage.md` resolve correctly.

## Prerequisites

- **Python 3.14+** (specified in `pyproject.toml`)
- **uv package manager** — [Installation guide](https://docs.astral.sh/uv/)
- **Playwright Chromium** — Install via `uv run playwright install chromium`
- **Groq API key** (for remote mode) — Get yours at [groq.com](https://groq.com/)
- **Ollama** (for local mode, optional) — [Download and install](https://ollama.com/)

### Setting up Ollama (optional)

If you want to use local LLMs:

1. Install Ollama from [ollama.com](https://ollama.com/)
2. Pull a model: `ollama pull llama3.2`
3. Start the server: `ollama serve` (usually runs automatically)
4. Set `LOCAL_MODEL_NAME=llama3.2` in `.env`
5. Use `is_local=True` in your code

## Usage examples

### Full pipeline (recommended)

Run the complete scraping and extraction pipeline:

```bash
uv run python scripts/main.py
```

This will:

1. Fetch the page specified in `SITE_URL`
2. Convert HTML to markdown and save to `data/webpage.md`
3. Extract structured data according to your schema
4. Export results to `data/data.csv`

### Scrape only (standalone)

If you only need to fetch and convert a page to markdown:

```python
import asyncio
from scripts.scraper import fetch_page, export_as_markdown

async def scrape_only():
    html = await fetch_page(
        url="https://example.com",
        wait_until="networkidle",
        timeout=30000
    )
    output_path = export_as_markdown(html)
    print(f"Markdown saved to: {output_path}")

asyncio.run(scrape_only())
```

### Extract only (from existing markdown)

If you already have a markdown file and want to extract data from it:

```python
from scripts import parser, main

# Requires data/webpage.md to exist
parser.extract_data_from_markdown(
    md_path="data/webpage.md",
    SYSTEM_PROMPT=main.SYSTEM_PROMPT,
    is_local=False,  # or True for Ollama
)
```

### Using the stealth scraper directly

For maximum control over scraping behavior:

```python
import asyncio
from scripts.scraper import StealthPlaywrightScraper

async def advanced_scrape():
    scraper = StealthPlaywrightScraper(
        headless=True,
        max_concurrent_browsers=5,
        proxy=None,  # or {"server": "http://proxy:8080", "username": "user", "password": "pass"}
        use_stealth=True,
    )

    await scraper.start()

    try:
        html = await scraper.fetch_page(
            url="https://example.com",
            wait_until="load",
            timeout=60000,
            retry_count=5,
            delay_between_retries=3.0,
            wait_for_selector=".main-content",  # Optional
            wait_for_timeout=1000,  # Optional additional wait in ms
        )
        print(f"Fetched {len(html)} characters")
    finally:
        await scraper.close()

asyncio.run(advanced_scrape())
```

### Concurrent multi-page scraping

Scrape multiple pages concurrently using the context manager:

```python
import asyncio
from scripts.scraper import StealthPlaywrightScraper

async def scrape_multiple():
    urls = ["https://example1.com", "https://example2.com", "https://example3.com"]

    async with StealthPlaywrightScraper(
        headless=True,
        max_concurrent_browsers=3,
        use_stealth=True,
    ) as scraper:
        tasks = [scraper.fetch_page(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for url, result in zip(urls, results):
            if isinstance(result, Exception):
                print(f"Failed to scrape {url}: {result}")
            else:
                print(f"Successfully scraped {url}: {len(result)} chars")

asyncio.run(scrape_multiple())
```

## LLM backends

| Feature                | Groq (remote)                   | Ollama (local)              |
| ---------------------- | ------------------------------- | --------------------------- |
| **Speed**              | Fast (cloud GPUs)               | Hardware-dependent          |
| **Privacy**            | Data sent to Groq               | Stays on your machine       |
| **Cost**               | API usage fees                  | Free (your compute)         |
| **Setup**              | `API_KEY` + `REMOTE_MODEL_NAME` | Ollama + `LOCAL_MODEL_NAME` |
| **Default chunk size** | 6,000 tokens                    | 1,500 tokens                |
| **Best for**           | Production, large-scale         | Development, sensitive data |

### Recommended models

**Groq:**

- `llama-3.3-70b-versatile` — Best balance of speed and quality
- `llama-3.1-8b-instant` — Fastest, good for simple extraction

**Ollama:**

- `llama3.2` — Good general-purpose model
- `mistral` — Fast and efficient
- `qwen2.5` — Excellent for structured output

Local chunks use a smaller default (1,500 tokens) to accommodate typical 7B–14B model context windows. Remote models with larger contexts can handle 6,000+ tokens per chunk.

## Token budget and chunking

The pipeline uses `tiktoken` with the `cl100k_base` encoding to estimate token counts. While this encoding is designed for OpenAI models, it provides a reasonable approximation for other models and helps prevent context window overflows.

### How chunking works

1. **Line-based splitting** — Text is split at line boundaries to preserve markdown structure
2. **Token counting** — Each line is counted using `tiktoken` before being added to a chunk
3. **Boundary respect** — Chunks never exceed `max_tokens`, creating a new chunk when necessary
4. **Oversized line handling** — Single lines exceeding `max_tokens` are placed in their own chunk

### Chunk size recommendations

| Scenario          | Recommended max_tokens | Reason                                |
| ----------------- | ---------------------- | ------------------------------------- |
| Local 7B models   | 1,500                  | Fits comfortably in 4K context        |
| Local 13B+ models | 3,000                  | Can handle larger contexts            |
| Groq cloud models | 6,000                  | Take advantage of larger contexts     |
| Dense content     | Lower values           | Ensures extraction doesn't miss items |
| Sparse content    | Higher values          | Reduces API calls                     |

### Monitoring token usage

Each chunk logs its estimated token count and the LLM usage:

```
Processing chunk 1/3 (Estimated tokens: 1847)
Usage: P:1847 C:324 T:2171
```

- **P** = Prompt tokens (your chunk + system prompt)
- **C** = Completion tokens (LLM's response)
- **T** = Total tokens (P + C)

Use this to optimize chunk sizes and estimate API costs.

## Stealth features explained

The `StealthPlaywrightScraper` class implements multiple anti-detection techniques to bypass bot detection systems:

### Browser fingerprint randomization

Each request uses randomized characteristics to avoid fingerprint tracking:

- **User agents** — Rotates between 5 recent Chrome, Firefox, and Safari user agents
- **Screen resolutions** — Randomly selects from common resolutions (1920×1080, 2560×1440, etc.)
- **Timezones** — Randomizes timezone IDs across major regions (US, Europe, Asia)
- **Geolocation** — Sets realistic geolocation coordinates (defaults to NYC)

### Anti-bot detection

- **Webdriver flag removal** — Overrides `navigator.webdriver` property
- **Chrome runtime injection** — Adds `window.chrome` object to mimic real Chrome
- **Plugin fingerprinting** — Provides realistic plugin list instead of empty array
- **Permission queries** — Intercepts and properly handles permission API calls
- **Language headers** — Sets realistic Accept-Language headers

### Request control

- **Custom headers** — Adds standard browser headers (Accept-Encoding, DNT, etc.)
- **Stealth plugin** — Applies `playwright-stealth` for additional protections
- **Launch arguments** — Disables automation flags and site isolation features
- **Retry logic** — Automatic retries with exponential backoff on failures
- **Semaphore-based concurrency** — Prevents resource exhaustion during concurrent scraping

### Usage notes

- Set `headless=False` for debugging (see the actual browser)
- Adjust `max_concurrent_browsers` based on your system resources
- Use proxies for IP rotation: `proxy={"server": "http://...", "username": "...", "password": "..."}`
- Set `use_stealth=False` only if the target doesn't have bot detection

## Tech stack

| Library                                                              | Version | Role                             |
| -------------------------------------------------------------------- | ------- | -------------------------------- |
| [Playwright](https://playwright.dev/python/)                         | 1.60+   | Headless browser automation      |
| [playwright-stealth](https://github.com/AtuboDad/playwright_stealth) | 2.0+    | Anti-detection and bot evasion   |
| [markdownify](https://github.com/matthewwithanm/python-markdownify)  | 1.2+    | HTML to Markdown conversion      |
| [Instructor](https://python.useinstructor.com/)                      | 1.15+   | Structured LLM output validation |
| [Pydantic](https://docs.pydantic.dev/)                               | 2.13+   | Schema definition and validation |
| [Groq](https://groq.com/)                                            | 1.2+    | Remote LLM inference (cloud)     |
| [OpenAI](https://openai.com/)                                        | —       | Ollama client compatibility      |
| [tiktoken](https://github.com/openai/tiktoken)                       | 0.13+   | Token counting and estimation    |
| [pandas](https://pandas.pydata.org/)                                 | 3.0+    | CSV export and data manipulation |
| [python-dotenv](https://github.com/theskumar/python-dotenv)          | 0.9+    | Environment variable management  |

All dependencies are specified in `pyproject.toml` and locked in `uv.lock` for reproducible builds.

## Troubleshooting

| Issue                                                          | Solution                                                                                                                                                              |
| -------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **`Input file not found: data/webpage.md`**                    | Run the scraper first, or ensure you're running from the repository root.                                                                                             |
| **`Model name not configured`**                                | Set `LOCAL_MODEL_NAME` (+ Ollama running) or `REMOTE_MODEL_NAME` + `API_KEY` in `.env`.                                                                               |
| **`playwright._impl._errors.Error: Executable doesn't exist`** | Install Chromium: `uv run playwright install chromium`                                                                                                                |
| **Empty CSV or missing rows**                                  | 1) Check `data/webpage.md` has content<br>2) Adjust `SYSTEM_PROMPT` to be more specific<br>3) Increase chunk size<br>4) Verify target page actually contains the data |
| **`Connection refused` (Ollama)**                              | 1) Start Ollama: `ollama serve`<br>2) Pull model: `ollama pull llama3.2`<br>3) Verify it's running on port 11434                                                      |
| **`TimeoutError` on `page.goto()`**                            | 1) Use `wait_until="load"` instead of `"networkidle"`<br>2) Increase `timeout` parameter<br>3) Use `wait_for_selector` for dynamic content                            |
| **Invalid JSON or validation errors**                          | 1) Make `SYSTEM_PROMPT` more strict<br>2) Add examples to the prompt<br>3) Set `max_retries=3` in `generate_output()` for production<br>4) Try a different model      |
| **Bot detection / 403 errors**                                 | 1) Ensure `use_stealth=True`<br>2) Add proxy configuration<br>3) Increase delays between requests<br>4) Try `headless=False` to debug                                 |
| **High memory usage**                                          | 1) Reduce `max_concurrent_browsers`<br>2) Decrease chunk size<br>3) Process fewer pages at once                                                                       |
| **Slow extraction**                                            | 1) Use Groq instead of local Ollama<br>2) Increase chunk size to reduce API calls<br>3) Use faster model (e.g., `llama-3.1-8b-instant`)                               |
| **Import errors**                                              | Ensure you're running from repo root: `uv run python scripts/main.py` (not `cd scripts && python main.py`)                                                            |

## Best practices

### Schema design

- **Be specific** — Define exact field types (str, int, HttpUrl, datetime, etc.)
- **Use Optional** — Mark fields that may not always be present as `Optional[type]`
- **Add descriptions** — Use docstrings and Field descriptions for better LLM understanding
- **Keep it simple** — Complex nested schemas are harder for LLMs to fill correctly

### System prompt engineering

- **Be explicit** — Tell the model exactly what format you want ("valid JSON object")
- **Prohibit extras** — Explicitly forbid markdown fences, explanations, and conversational text
- **Provide examples** — Show 1-2 example outputs in the prompt for complex schemas
- **Define edge cases** — Explain how to handle missing data, ambiguous fields, etc.

### Performance optimization

- **Right-size chunks** — Larger chunks = fewer API calls but may miss edge cases
- **Use remote for production** — Groq is significantly faster than local Ollama
- **Cache markdown** — Save `webpage.md` and iterate on extraction without re-scraping
- **Batch similar pages** — Process multiple pages with the same schema together
- **Monitor token usage** — Use the logged token counts to optimize costs

### Scraping considerations

- **Respect robots.txt** — Check if scraping is allowed before targeting a site
- **Rate limiting** — Add delays between requests to avoid overwhelming servers
- **Error handling** — Always handle exceptions and implement retry logic
- **Session persistence** — For authenticated scraping, reuse browser contexts
- **Legal compliance** — Ensure your use case complies with terms of service and local laws

### Data quality

- **Validate output** — Check `data/data.csv` after extraction for accuracy
- **Test on samples** — Try different pages to ensure schema generalization
- **Handle duplicates** — Implement deduplication if processing multiple pages
- **Version your schemas** — Track changes to extraction schemas over time

## Performance benchmarks

Approximate performance on a typical product listing page (50KB HTML, 5KB markdown):

| Configuration               | Scrape time | Extract time | Total | Cost (per page) |
| --------------------------- | ----------- | ------------ | ----- | --------------- |
| Groq (llama-3.3-70b)        | 5s          | 2s           | 7s    | ~$0.0001        |
| Groq (llama-3.1-8b)         | 5s          | 1s           | 6s    | ~$0.00005       |
| Ollama (llama3.2, M1 Mac)   | 5s          | 15s          | 20s   | Free            |
| Ollama (llama3.2, RTX 4090) | 5s          | 8s           | 13s   | Free            |

_Times and costs are estimates and will vary based on page complexity and infrastructure._

## Contributing

This project is near completion. If you encounter bugs or have suggestions for improvements, feel free to open an issue or submit a pull request.

## License

Provided as-is for educational and personal use. No warranty is expressed or implied.
