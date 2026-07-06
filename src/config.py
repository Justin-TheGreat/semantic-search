import os

# pyrefly: ignore [missing-import]
from pydantic_settings import BaseSettings


def get_secret(name: str, default: str = "") -> str:
    """Read secret from file (Docker secrets) or env var (dev)."""
    path = os.environ.get(f"{name}_FILE")
    if path and os.path.exists(path):
        with open(path) as f:
            return f.read().strip()
    return os.environ.get(name, default)


class Settings(BaseSettings):
    env: str = "development"
    log_level: str = "INFO"
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    model_cache_dir: str = "/models"
    qdrant_host: str = "qdrant"
    qdrant_port: int = 6333
    qdrant_collection: str = "articles"
    db_host: str = "db"
    db_port: int = 5432
    db_user: str = "searchuser"
    db_name: str = "searchdb"
    redis_host: str = "redis"
    redis_port: int = 6379
    cache_ttl_seconds: int = 300

    # --- LLM serving (Phase 2) ---
    vllm_base_url: str = "http://vllm:8000/v1"
    vllm_model: str = "Qwen/Qwen2.5-0.5B-Instruct"
    llm_max_tokens: int = 512
    llm_temperature: float = 0.1

    # --- Hybrid retrieval & reranking (Phase 3) ---
    enable_hybrid: bool = True
    sparse_model: str = "Qdrant/bm25"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    retrieve_candidates: int = 50
    rerank_top_k: int = 8
    chunk_size: int = 512
    chunk_overlap: int = 64

    # --- Agent (Phase 4) ---
    max_agent_attempts: int = 2

    # --- LLMOps (Phase 5) ---
    semantic_cache_threshold: float = 0.97
    semantic_cache_ttl_seconds: int = 3600

    # --- Observability (Phase 6) ---
    otel_enabled: bool = False
    langfuse_enabled: bool = False

    @property
    def db_password(self) -> str:
        return get_secret("DB_PASSWORD", "localdev")

    @property
    def db_url(self) -> str:
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


settings = Settings()
