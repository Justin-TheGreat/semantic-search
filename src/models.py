from pydantic import BaseModel, Field
from typing import List


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