import asyncio, os, time
import scraper
import parser
import playwright_scraper
from dotenv import load_dotenv
from pydantic import BaseModel, HttpUrl


load_dotenv()

SITE_URL = os.getenv("SITE_URL")


# Strict instructions to ensure the LLM focuses purely on data extraction
# and does not include conversational filler which could break JSON parsing.
SYSTEM_PROMPT = """
You are a data extraction assistant.
Respond ONLY with a valid JSON object. No explanation, no markdown fences.
Extract only the key information from the given content.
"""

class Schema(BaseModel):
    """Schema for a single extracted data."""
    url: HttpUrl


async def main():
    # Use stealth Playwright scraper for maximum stealth and scaling
    html_content = await playwright_scraper.fetch_page(
        url=SITE_URL, wait_until="networkidle"
    )
    output_path = scraper.export_as_markdown(html_content)
    
    parser.extract_data_from_markdown(
        md_path=output_path, SYSTEM_PROMPT=SYSTEM_PROMPT, is_local=False
    )


if __name__ == "__main__":
    start_time = time.time()
    asyncio.run(main())
    print(f"✅ Run Time is {time.time() - start_time:.2f} seconds")
