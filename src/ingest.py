import json
import sys
from pathlib import Path
# pyrefly: ignore [missing-import]
import psycopg
# pyrefly: ignore [missing-import]
from sentence_transformers import SentenceTransformer
# pyrefly: ignore [missing-import]
from qdrant_client import QdrantClient
# pyrefly: ignore [missing-import]
from qdrant_client.models import PointStruct, VectorParams, Distance
# pyrefly: ignore [missing-import]
from src.config import settings


DDL = """
CREATE TABLE IF NOT EXISTS articles (
    article_id TEXT PRIMARY KEY,
    title      TEXT NOT NULL,
    snippet    TEXT NOT NULL,
    body       TEXT NOT NULL
);
"""


def main(jsonl_path: str = "/app/data/articles.jsonl"):
    print(f"Loading articles from {jsonl_path}")
    path = Path(jsonl_path)
    if not path.exists():
        print(f"File not found: {jsonl_path}", file=sys.stderr)
        sys.exit(1)

    articles = [json.loads(line) for line in path.read_text().splitlines()]
    print(f"  {len(articles)} articles")

    # Create table
    with psycopg.connect(settings.db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(DDL)
        conn.commit()

    # Embed and insert
    model = SentenceTransformer(
        settings.model_name,
        cache_folder=settings.model_cache_dir,
    )
    qdrant = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)

    # Ensure collection
    collections = [c.name for c in qdrant.get_collections().collections]
    if settings.qdrant_collection not in collections:
        qdrant.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE),
        )

    texts = [f"{a['title']}. {a['body']}" for a in articles]
    print("  Encoding...")
    vectors = model.encode(texts, show_progress_bar=True, batch_size=16)

    print("  Inserting...")
    points = [
        PointStruct(
            id=i,
            vector=vec.tolist(),
            payload={"article_id": a["article_id"]},
        )
        for i, (a, vec) in enumerate(zip(articles, vectors))
    ]
    qdrant.upsert(collection_name=settings.qdrant_collection, points=points)

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