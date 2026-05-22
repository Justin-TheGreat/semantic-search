from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from sentence_transformers import SentenceTransformer
from src.config import settings
from src.models import HealthResponse, SearchRequest, SearchResponse
from src.search import SearchService
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response
from src.metrics import search_requests, search_latency
import time

model: SentenceTransformer | None = None
service: SearchService | None = None


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

# Update the /search handler:
@app.post("/search", response_model=SearchResponse)
async def search(req: SearchRequest) -> SearchResponse:
    if service is None:
        raise HTTPException(503, "Service not ready")
    start = time.time()
    hits, cached = service.search(req.query, req.limit)
    search_latency.observe(time.time() - start)
    search_requests.labels(cached=str(cached)).inc()
    return SearchResponse(query=req.query, hits=hits, cached=cached)






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