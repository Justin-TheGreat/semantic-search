from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from sentence_transformers import SentenceTransformer
from src.config import settings
from src.models import HealthResponse, SearchRequest, SearchResponse
from src.search import SearchService

model: SentenceTransformer | None = None
service: SearchService | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global model, service
    print(f"Loading model: {settings.model_name}")
    model = SentenceTransformer(
        settings.model_name,
        cache_folder=settings.model_cache_dir,
    )
    service = SearchService(model)
    service.ensure_collection()
    print("Ready.")
    yield


app = FastAPI(title="Semantic Search API", lifespan=lifespan)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", model_loaded=model is not None)


@app.post("/search", response_model=SearchResponse)
async def search(req: SearchRequest) -> SearchResponse:
    if service is None:
        raise HTTPException(503, "Service not ready")
    hits, cached = service.search(req.query, req.limit)
    return SearchResponse(query=req.query, hits=hits, cached=cached)