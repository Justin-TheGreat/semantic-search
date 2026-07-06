from typing import List

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    limit: int = Field(default=10, ge=1, le=50)


class SearchHit(BaseModel):
    article_id: str
    title: str
    snippet: str
    score: float


class SearchResponse(BaseModel):
    query: str
    hits: List[SearchHit]
    cached: bool = False


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool


class ReadyResponse(BaseModel):
    ready: bool


class ChatRequest(BaseModel):
    # Guardrail: oversized queries are rejected with 422 before touching the LLM.
    query: str = Field(..., min_length=1, max_length=500)


class ChatAnswer(BaseModel):
    answer: str
    citations: List[str]
    verified: bool
    prompt_version: str
    cached: bool = False
