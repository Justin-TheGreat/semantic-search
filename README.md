# Semantic Search Engine

A Dockerized semantic search API over Wikipedia articles.

Stack: FastAPI · sentence-transformers · Qdrant · PostgreSQL · Redis · nginx

## Quick start

```
# create secrets
echo "changeme_strong_password" > secrets/db_password.txt

# generate self-signed TLS cert
bash nginx/generate-certs.sh

# start the stack
docker compose up -d

# ingest sample data
docker compose exec api python -m src.ingest

# search!
curl -k https://localhost/search?q=machine+learning
```

## Architecture

(diagram + service descriptions go here)
