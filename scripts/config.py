from __future__ import annotations

from typing import List
from pydantic import BaseModel, HttpUrl


SYSTEM_PROMPT = """
You are a data extraction assistant.
Respond ONLY with a valid JSON object. No explanation, no markdown fences.
Extract only the key information from the given content.
"""

class Schema(BaseModel):
    """Schema for a single extracted data."""

    url: HttpUrl

class SchemaCollection(BaseModel):
    """Container for multiple extracted datas, used to enforce structured LLM output."""

    collections: List[Schema]