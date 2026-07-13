import asyncio
import os
import time

from dotenv import load_dotenv

import scraper
from parser import extract_data_from_markdown


load_dotenv()

SITE_URL = os.getenv("SITE_URL")


async def main():
    # Use stealth Playwright scraper for maximum stealth and scaling
    html_content = await scraper.fetch_page(
        url=SITE_URL, wait_until="networkidle"
    )
    output_path = scraper.export_as_markdown(html_content)
    
    extract_data_from_markdown(
        md_path=output_path, is_local=False
    )


if __name__ == "__main__":
    start_time = time.time()
    asyncio.run(main())
    print(f"✅ Run Time is {time.time() - start_time:.2f} seconds")
