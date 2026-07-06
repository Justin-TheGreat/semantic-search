"""LLM semantic cache: reuse answers for near-duplicate questions.

Keys on the *embedding* of the normalized question, not the raw string, so
"what is docker?" and "What is Docker" hit the same entry. Entries live in the
same Redis the search cache uses.
"""
import hashlib
import json

import numpy as np
import redis

from src.config import settings
from src.metrics import semantic_cache_hits, semantic_cache_misses


class SemanticCache:
    def __init__(self, model, redis_client: redis.Redis | None = None):
        self.model = model
        self.redis = redis_client or redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            decode_responses=True,
        )

    @staticmethod
    def _normalize(question: str) -> str:
        return " ".join(question.lower().split())

    def get(self, question: str) -> dict | None:
        query_vec = np.asarray(self.model.encode(self._normalize(question)), dtype=np.float32)
        query_norm = float(np.linalg.norm(query_vec)) + 1e-9
        best_payload, best_sim = None, 0.0
        for key in self.redis.scan_iter(match="semcache:*", count=200):
            raw = self.redis.get(key)
            if not raw:
                continue
            entry = json.loads(raw)
            vec = np.asarray(entry["vector"], dtype=np.float32)
            sim = float(np.dot(query_vec, vec) / (query_norm * (np.linalg.norm(vec) + 1e-9)))
            if sim > best_sim:
                best_sim, best_payload = sim, entry["payload"]
        if best_payload is not None and best_sim >= settings.semantic_cache_threshold:
            semantic_cache_hits.inc()
            return best_payload
        semantic_cache_misses.inc()
        return None

    def set(self, question: str, payload: dict) -> None:
        normalized = self._normalize(question)
        vec = self.model.encode(normalized).tolist()
        key = f"semcache:{hashlib.md5(normalized.encode()).hexdigest()}"
        self.redis.setex(
            key,
            settings.semantic_cache_ttl_seconds,
            json.dumps({"vector": vec, "payload": payload}),
        )
