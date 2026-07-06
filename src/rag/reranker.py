from dataclasses import replace

from src.config import settings
from src.rag.retriever import RetrievedDoc


class Reranker:
    """Cross-encoder second-stage ranker: precise scoring of (query, passage) pairs."""

    def __init__(self):
        self._ce = None

    @property
    def ce(self):
        if self._ce is None:
            from sentence_transformers import CrossEncoder

            self._ce = CrossEncoder(settings.reranker_model)
        return self._ce

    def rerank(
        self, query: str, docs: list[RetrievedDoc], top_k: int | None = None
    ) -> list[RetrievedDoc]:
        if not docs:
            return []
        top_k = top_k or settings.rerank_top_k
        # One batched predict call over all pairs (fast on CPU).
        scores = self.ce.predict([(query, d.text) for d in docs])
        ranked = sorted(zip(docs, scores), key=lambda pair: -float(pair[1]))
        return [replace(d, score=float(s)) for d, s in ranked[:top_k]]
