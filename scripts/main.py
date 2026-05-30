import asyncio, os, time
import scraper
import parser
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


def main():

    parser.extract_data_from_markdown(
        md_path="data/webpage.md", SYSTEM_PROMPT=SYSTEM_PROMPT, is_local=True
    )


if __name__ == "__main__":
    start_time = time.time()
    main()
    print(f"✅ Run Time is {time.time() - start_time:.2f} seconds")
