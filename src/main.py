from contextlib import asynccontextmanager
from fastapi import FastAPI
from sentence_transformers import SentenceTransformer
from src.config import settings
from src.models import HealthResponse

# Will hold the loaded model across requests
model: SentenceTransformer | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load model on startup, clean up on shutdown."""
    global model
    print(f"Loading model: {settings.model_name}")
    model = SentenceTransformer(
        settings.model_name,
        cache_folder=settings.model_cache_dir,
    )
    print("Model loaded.")
    yield
    print("Shutting down.")


app = FastAPI(title="Semantic Search API", lifespan=lifespan)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        model_loaded=model is not None,
    )