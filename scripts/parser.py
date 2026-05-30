"""
Module for extracting structural data from Markdown content using LLMs.

This module utilizes the Instructor library to enforce structured output (JSON)
via Pydantic models. It supports both local (Ollama) and remote (Groq) LLM backends.
"""

import os, time
import instructor, tiktoken
import pandas as pd
from groq import Groq
from openai import OpenAI
from pydantic import BaseModel
from typing import List, Optional, Tuple
from dotenv import load_dotenv
import main

load_dotenv()

API_KEY = os.getenv("API_KEY")
LOCAL_MODEL_NAME = os.getenv("LOCAL_MODEL_NAME")
REMOTE_MODEL_NAME = os.getenv("REMOTE_MODEL_NAME")

class SchemaCollection(BaseModel):
    """Container for multiple extracted datas, used to enforce structured LLM output."""

    collections: List[main.Schema]

def main() -> None:
    extract_data_from_markdown(is_local=False)


def extract_data_from_markdown(md_path: str, SYSTEM_PROMPT: str = None, is_local: bool = False) -> None:
    """
    Extracts data from scraped markdown and exports the results to a CSV file.
    """
    if not os.path.exists(md_path):
        print(f"❌ Input file not found: {md_path}")
        return

    with open(md_path, "r", encoding="utf-8") as file:
        markdown_content = file.read()

    # Determine chunk size based on model context limits.
    # Remote models often handle larger contexts more efficiently.
    if is_local:
        chunks = chunk_text(markdown_content)
    else:
        chunks = chunk_text(markdown_content, max_tokens=6000)

    print(f"Total chunks to process: {len(chunks)}")

    client, model_name = initialize_client(is_local=is_local)
    all_urls = []

    for i, chunk in enumerate(chunks):
        print(
            f"Processing chunk {i+1}/{len(chunks)} (Estimated tokens: {count_tokens(chunk)})"
        )
        results = generate_output(
            client=client,
            SYSTEM_PROMPT=SYSTEM_PROMPT,
            prompt=chunk,
            model_name=model_name,
        )
        if results and results.collections:
            all_urls.extend(results.collections)

    # Consolidate and export all extracted results to a persistent file.
    final_collection = SchemaCollection(collections=all_urls)
    export_data(final_collection)


def initialize_client(is_local: bool) -> Tuple[instructor.Instructor, Optional[str]]:
    """
    Configures the API client and selects the appropriate model.

    If local, it connects to a local Ollama instance.
    If remote, it uses the Groq API for high-performance inference.
    """
    if is_local:
        # Connect to local Ollama server via OpenAI-compatible endpoint
        openai_client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
        client = instructor.from_openai(openai_client, mode=instructor.Mode.JSON)
        model_name = LOCAL_MODEL_NAME
    else:
        # Use Groq for faster remote execution
        client = instructor.from_groq(Groq(api_key=API_KEY), mode=instructor.Mode.JSON)
        model_name = REMOTE_MODEL_NAME

    return client, model_name


def generate_output(
    client: instructor.Instructor, SYSTEM_PROMPT: str, prompt: str, model_name: str
) -> Optional[SchemaCollection]:
    """
    Sends a prompt to the LLM and returns a structured Pydantic object.

    Enforces a strict schema using the Instructor library to ensure
    the output is always a valid LinkCollection.
    """
    if not model_name:
        print("⚠️ Model name not configured.")
        return None
    if not SYSTEM_PROMPT:
        SYSTEM_PROMPT = """
            You are a data extraction assistant.
            Respond ONLY with a valid JSON object. No explanation, no markdown fences.
            """

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    # Temperature is set to 0.0 to ensure maximum consistency and
    # minimize 'hallucinations' in the extracted data.
    try:
        response, completion = client.chat.completions.create_with_completion(
            model=model_name,
            messages=messages,
            temperature=0.0,
            response_model=SchemaCollection,
            max_tokens=8192,
            max_retries=0,  # retries should be 3 for production
        )

        print(
            f"Usage: P:{completion.usage.prompt_tokens} C:{completion.usage.completion_tokens} T:{completion.usage.total_tokens}"
        )
        return response
    except Exception as e:
        print(f"❌ Error during generation: {e}")
        return None


def export_data(results: SchemaCollection) -> None:
    """
    Saves the extracted URLs to a text file.

    Outputs one URL per line to simplify integration with downstream
    tools like download managers or web crawlers.
    """
    output_path = "data/data.csv"
    df = pd.DataFrame([vars(obj) for obj in results.collections])
    df.to_csv(output_path, index=False)

    print(f"✅ URLs extracted successfully to {output_path}")


def count_tokens(text: str) -> int:
    """
    Estimates the number of tokens in a string using the tiktoken library.

    This is essential for monitoring API costs and ensuring that
    prompts stay within the model's maximum context window.
    """
    encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))


def chunk_text(text: str, max_tokens: int = 1000) -> List[str]:
    """
    Splits long text into smaller chunks based on token count.

    The chunking logic attempts to split at line breaks to preserve
    the structural context of the markdown content.
    """
    lines = text.splitlines()
    chunks = []
    current_chunk = []
    current_tokens = 0

    for line in lines:
        # Add 1 for the newline character that would be added back by join()
        line_tokens = count_tokens(line) + 1

        # Handle edge case where a single line exceeds the max tokens.
        if line_tokens > max_tokens:
            if current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = []
                current_tokens = 0
            chunks.append(line)
            continue

        if current_tokens + line_tokens > max_tokens:
            chunks.append("\n".join(current_chunk))
            current_chunk = [line]
            current_tokens = line_tokens
        else:
            current_chunk.append(line)
            current_tokens += line_tokens

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks


if __name__ == "__main__":
    start_time = time.time()
    main()
    print(f"✅ Run Time is {time.time() - start_time:.2f} seconds")
