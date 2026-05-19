import json
import hashlib
from typing import List
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
import redis
import psycopg
from src.config import settings
from src.models import SearchHit


class SearchService:
    def __init__(self, model: SentenceTransformer):
        self.model = model
        self.qdrant = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
        )
        self.redis = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            decode_responses=True,
        )

    def ensure_collection(self):
        """Create Qdrant collection if it doesn't exist."""
        collections = self.qdrant.get_collections().collections
        if settings.qdrant_collection not in [c.name for c in collections]:
            self.qdrant.create_collection(
                collection_name=settings.qdrant_collection,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE),
            )

    def search(self, query: str, limit: int) -> tuple[List[SearchHit], bool]:
        cache_key = f"search:{hashlib.md5(f'{query}:{limit}'.encode()).hexdigest()}"
        cached = self.redis.get(cache_key)
        if cached:
            return [SearchHit(**h) for h in json.loads(cached)], True

        # Generate query embedding
        query_vector = self.model.encode(query).tolist()

        # Search Qdrant
        results = self.qdrant.search(
            collection_name=settings.qdrant_collection,
            query_vector=query_vector,
            limit=limit,
        )

        # Fetch metadata from Postgres
        article_ids = [r.payload["article_id"] for r in results]
        with psycopg.connect(settings.db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT article_id, title, snippet FROM articles "
                    "WHERE article_id = ANY(%s)",
                    (article_ids,),
                )
                meta = {row[0]: (row[1], row[2]) for row in cur.fetchall()}

        hits = []
        for r in results:
            aid = r.payload["article_id"]
            if aid in meta:
                title, snippet = meta[aid]
                hits.append(SearchHit(
                    article_id=aid,
                    title=title,
                    snippet=snippet,
                    score=r.score,
                ))

        # Cache result
        self.redis.setex(
            cache_key,
            settings.cache_ttl_seconds,
            json.dumps([h.model_dump() for h in hits]),
        )
        return hits, False