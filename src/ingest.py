import json
import os
import sys
from pathlib import Path

# pyrefly: ignore [missing-import]
import psycopg

# pyrefly: ignore [missing-import]
from qdrant_client import QdrantClient, models

# pyrefly: ignore [missing-import]
from sentence_transformers import SentenceTransformer

# pyrefly: ignore [missing-import]
from src.config import settings
from src.rag.chunking import chunk_text

DDL = """
CREATE TABLE IF NOT EXISTS articles (
    article_id TEXT PRIMARY KEY,
    title      TEXT NOT NULL,
    snippet    TEXT NOT NULL,
    body       TEXT NOT NULL
);
"""


def recreate_collection(qdrant: QdrantClient):
    """Drop + create so the schema switch (unnamed -> named+sparse vectors) is clean."""
    collections = [c.name for c in qdrant.get_collections().collections]
    if settings.qdrant_collection in collections:
        qdrant.delete_collection(settings.qdrant_collection)
    qdrant.create_collection(
        collection_name=settings.qdrant_collection,
        vectors_config={
            "dense": models.VectorParams(size=384, distance=models.Distance.COSINE),
        },
        sparse_vectors_config={"sparse": models.SparseVectorParams()},
    )


def main(jsonl_path: str = "/app/data/articles.jsonl"):
    print(f"Loading articles from {jsonl_path}")
    path = Path(jsonl_path)
    if not path.exists():
        print(f"File not found: {jsonl_path}", file=sys.stderr)
        sys.exit(1)

    articles = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    print(f"  {len(articles)} articles")

    # Create metadata table
    with psycopg.connect(settings.db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(DDL)
        conn.commit()

    # Chunk bodies into overlapping windows — retrieval works on focused passages.
    chunks: list[dict] = []
    for a in articles:
        pieces = chunk_text(
            f"{a['title']}. {a['body']}",
            size=settings.chunk_size,
            overlap=settings.chunk_overlap,
        )
        for i, text in enumerate(pieces):
            chunks.append(
                {
                    "article_id": a["article_id"],
                    "chunk_id": f"{a['article_id']}-c{i}",
                    "title": a["title"],
                    "text": text,
                }
            )
    print(f"  {len(chunks)} chunks")

    # Dual embeddings: dense (semantic) + sparse BM25 (keyword)
    model = SentenceTransformer(
        settings.model_name,
        cache_folder=settings.model_cache_dir,
    )
    from fastembed import SparseTextEmbedding

    sparse_model = SparseTextEmbedding(
        settings.sparse_model,
        cache_dir=os.path.join(settings.model_cache_dir, "fastembed"),
    )

    texts = [c["text"] for c in chunks]
    print("  Encoding dense...")
    dense_vecs = model.encode(texts, show_progress_bar=True, batch_size=16)
    print("  Encoding sparse...")
    sparse_vecs = list(sparse_model.embed(texts))

    qdrant = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
    recreate_collection(qdrant)

    print("  Inserting into Qdrant...")
    points = [
        models.PointStruct(
            id=i,
            vector={
                "dense": dv.tolist(),
                "sparse": models.SparseVector(
                    indices=sv.indices.tolist(),
                    values=sv.values.tolist(),
                ),
            },
            payload=chunk,
        )
        for i, (chunk, dv, sv) in enumerate(zip(chunks, dense_vecs, sparse_vecs))
    ]
    qdrant.upsert(collection_name=settings.qdrant_collection, points=points)

    print("  Inserting metadata into Postgres...")
    with psycopg.connect(settings.db_url) as conn:
        with conn.cursor() as cur:
            for a in articles:
                cur.execute(
                    "INSERT INTO articles (article_id, title, snippet, body) "
                    "VALUES (%s, %s, %s, %s) ON CONFLICT (article_id) DO NOTHING",
                    (a["article_id"], a["title"], a["snippet"], a["body"]),
                )
        conn.commit()

    print("Done!")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/app/data/articles.jsonl")
