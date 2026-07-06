import os
from dataclasses import dataclass

from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer

from src.config import settings


@dataclass
class RetrievedDoc:
    article_id: str
    chunk_id: str
    title: str
    text: str
    score: float


class HybridRetriever:
    """Two-channel retriever: dense (MiniLM) + sparse (BM25) fused with RRF."""

    def __init__(self, model: SentenceTransformer, client: QdrantClient | None = None):
        self.model = model
        self.client = client or QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
        )
        self._sparse = None

    @property
    def sparse_model(self):
        # Lazy: downloading the BM25 model only happens on first hybrid call.
        if self._sparse is None:
            from fastembed import SparseTextEmbedding

            self._sparse = SparseTextEmbedding(
                settings.sparse_model,
                cache_dir=os.path.join(settings.model_cache_dir, "fastembed"),
            )
        return self._sparse

    def ensure_collection(self):
        """Create the collection with named dense + sparse vectors if missing."""
        collections = [c.name for c in self.client.get_collections().collections]
        if settings.qdrant_collection not in collections:
            self.client.create_collection(
                collection_name=settings.qdrant_collection,
                vectors_config={
                    "dense": models.VectorParams(size=384, distance=models.Distance.COSINE),
                },
                sparse_vectors_config={"sparse": models.SparseVectorParams()},
            )

    def _to_doc(self, point) -> RetrievedDoc:
        p = point.payload or {}
        return RetrievedDoc(
            article_id=p.get("article_id", ""),
            chunk_id=p.get("chunk_id", ""),
            title=p.get("title", ""),
            text=p.get("text", ""),
            score=point.score if point.score is not None else 0.0,
        )

    def dense_search(self, query: str, limit: int) -> list[RetrievedDoc]:
        vec = self.model.encode(query).tolist()
        res = self.client.query_points(
            collection_name=settings.qdrant_collection,
            query=vec,
            using="dense",
            limit=limit,
            with_payload=True,
        )
        return [self._to_doc(p) for p in res.points]

    def hybrid_search(self, query: str, limit: int | None = None) -> list[RetrievedDoc]:
        """Dense + sparse prefetch merged with Reciprocal Rank Fusion."""
        limit = limit or settings.retrieve_candidates
        dense_vec = self.model.encode(query).tolist()
        sparse_vec = next(iter(self.sparse_model.embed([query])))
        res = self.client.query_points(
            collection_name=settings.qdrant_collection,
            prefetch=[
                models.Prefetch(query=dense_vec, using="dense", limit=limit),
                models.Prefetch(
                    query=models.SparseVector(
                        indices=sparse_vec.indices.tolist(),
                        values=sparse_vec.values.tolist(),
                    ),
                    using="sparse",
                    limit=limit,
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=limit,
            with_payload=True,
        )
        return [self._to_doc(p) for p in res.points]

    def retrieve(self, query: str, limit: int | None = None) -> list[RetrievedDoc]:
        if settings.enable_hybrid:
            return self.hybrid_search(query, limit)
        return self.dense_search(query, limit or settings.rerank_top_k)
