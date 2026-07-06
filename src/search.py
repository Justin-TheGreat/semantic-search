import hashlib
import json
from typing import List

import psycopg
import redis
from sentence_transformers import SentenceTransformer

from src.config import settings
from src.models import SearchHit
from src.rag.reranker import Reranker
from src.rag.retriever import HybridRetriever, RetrievedDoc


class SearchService:
    def __init__(
        self,
        model: SentenceTransformer,
        retriever: HybridRetriever | None = None,
        reranker: Reranker | None = None,
    ):
        self.model = model
        self.retriever = retriever or HybridRetriever(model)
        self.reranker = reranker or Reranker()
        self.redis = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            decode_responses=True,
        )

    def ensure_collection(self):
        self.retriever.ensure_collection()

    def search(self, query: str, limit: int) -> tuple[List[SearchHit], bool]:
        # Mode is part of the key so flipping ENABLE_HYBRID never serves stale results.
        mode = "hybrid" if settings.enable_hybrid else "dense"
        cache_key = f"search:{mode}:{hashlib.md5(f'{query}:{limit}'.encode()).hexdigest()}"
        cached = self.redis.get(cache_key)
        if cached:
            return [SearchHit(**h) for h in json.loads(cached)], True

        if settings.enable_hybrid:
            candidates = self.retriever.hybrid_search(query)
            docs = self.reranker.rerank(
                query, candidates, top_k=max(limit, settings.rerank_top_k)
            )
        else:
            docs = self.retriever.dense_search(query, limit)

        # Collapse chunk-level hits to article level, keeping each article's best chunk.
        best: dict[str, RetrievedDoc] = {}
        order: list[str] = []
        for d in docs:
            if d.article_id and d.article_id not in best:
                best[d.article_id] = d
                order.append(d.article_id)
        article_ids = order[:limit]

        meta: dict[str, tuple[str, str]] = {}
        if article_ids:
            with psycopg.connect(settings.db_url) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT article_id, title, snippet FROM articles "
                        "WHERE article_id = ANY(%s)",
                        (article_ids,),
                    )
                    meta = {row[0]: (row[1], row[2]) for row in cur.fetchall()}

        hits = []
        for aid in article_ids:
            if aid in meta:
                title, snippet = meta[aid]
                hits.append(
                    SearchHit(
                        article_id=aid,
                        title=title,
                        snippet=snippet,
                        score=best[aid].score,
                    )
                )

        self.redis.setex(
            cache_key,
            settings.cache_ttl_seconds,
            json.dumps([h.model_dump() for h in hits]),
        )
        return hits, False
