import os
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