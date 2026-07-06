import json
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response, StreamingResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sentence_transformers import SentenceTransformer
from starlette.concurrency import run_in_threadpool

from src.config import settings
from src.metrics import chat_latency, chat_requests, search_latency, search_requests
from src.models import (
    ChatRequest,
    HealthResponse,
    ReadyResponse,
    SearchRequest,
    SearchResponse,
)
from src.rag.cache import SemanticCache
from src.rag.graph import RAGAgent
from src.rag.reranker import Reranker
from src.rag.retriever import HybridRetriever
from src.search import SearchService

model: SentenceTransformer | None = None
service: SearchService | None = None
agent: RAGAgent | None = None
semantic_cache: SemanticCache | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global model, service, agent, semantic_cache
    print(f"Loading model: {settings.model_name}")
    model = SentenceTransformer(
        settings.model_name,
        cache_folder=settings.model_cache_dir,
    )
    retriever = HybridRetriever(model)
    retriever.ensure_collection()
    reranker = Reranker()
    service = SearchService(model, retriever, reranker)
    agent = RAGAgent(retriever, reranker)
    semantic_cache = SemanticCache(model)
    print("Ready.")
    yield


app = FastAPI(title="Semantic Search API", lifespan=lifespan)

if settings.otel_enabled:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
    except ImportError:
        print("OTEL_ENABLED is set but opentelemetry packages are missing; skipping")


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness: the process is up (k8s restarts the pod if this fails)."""
    return HealthResponse(status="ok", model_loaded=model is not None)


@app.get("/ready", response_model=ReadyResponse)
async def ready() -> ReadyResponse:
    """Readiness: dependencies wired, safe to receive traffic."""
    if service is None or agent is None:
        raise HTTPException(503, "Service not ready")
    return ReadyResponse(ready=True)


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/search", response_model=SearchResponse)
async def search(req: SearchRequest) -> SearchResponse:
    if service is None:
        raise HTTPException(503, "Service not ready")
    start = time.time()
    hits, cached = await run_in_threadpool(service.search, req.query, req.limit)
    search_latency.observe(time.time() - start)
    search_requests.labels(cached=str(cached)).inc()
    return SearchResponse(query=req.query, hits=hits, cached=cached)


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


async def _chat_events(question: str):
    start = time.time()
    try:
        cached_payload = await run_in_threadpool(semantic_cache.get, question)
    except Exception:
        cached_payload = None  # cache is an optimization, never a hard dependency
    if cached_payload is not None:
        chat_requests.labels(cached="True").inc()
        yield _sse({"token": cached_payload.get("answer", "")})
        yield _sse({"event": "done", **cached_payload, "cached": True})
        chat_latency.observe(time.time() - start)
        return

    final = None
    try:
        async for ev in agent.astream_chat(question):
            if ev.get("event") == "done":
                final = ev
                yield _sse({**ev, "cached": False})
            else:
                yield _sse(ev)
    except Exception as exc:
        yield _sse({"event": "error", "detail": str(exc)})
        return
    chat_requests.labels(cached="False").inc()
    chat_latency.observe(time.time() - start)

    if final and final.get("answer"):
        payload = {
            "answer": final["answer"],
            "citations": final.get("citations", []),
            "verified": final.get("verified", False),
            "prompt_version": final.get("prompt_version", ""),
        }
        try:
            await run_in_threadpool(semantic_cache.set, question, payload)
        except Exception:
            pass


@app.post("/chat")
async def chat(req: ChatRequest):
    """Agentic RAG answer, streamed as Server-Sent Events."""
    if agent is None or semantic_cache is None:
        raise HTTPException(503, "Service not ready")
    return StreamingResponse(_chat_events(req.query), media_type="text/event-stream")
