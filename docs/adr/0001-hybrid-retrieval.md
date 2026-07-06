# ADR 0001 — Hybrid (dense + sparse) retrieval with cross-encoder reranking

**Status:** accepted

## Context

The baseline `/search` used pure dense retrieval (MiniLM 384-dim cosine).
Dense-only retrieval misses keyword-precise queries (exact names, acronyms) and
whole-document embeddings dilute relevance for RAG, where the LLM needs focused
passages.

## Decision

1. **Chunk** documents into overlapping word windows (512/64) at ingest time —
   one Qdrant point per chunk, payload carries the chunk text.
2. Store **named vectors** per point: `dense` (MiniLM) + `sparse` (FastEmbed
   BM25), and fuse the two result lists with **Reciprocal Rank Fusion** via
   Qdrant's Query API (`prefetch` + `FusionQuery`).
3. Rerank the fused top-50 with a **cross-encoder**
   (`ms-marco-MiniLM-L-6-v2`) down to top-8 — the standard two-stage
   retrieve→rerank production shape. Runs fine on CPU.
4. Everything is behind `ENABLE_HYBRID` so the old dense path remains one env
   var away (instant rollback, A/B comparison).

## Consequences

- Qdrant server and client had to move to ≥1.12 (Query API requirement).
- Ingest recreates the collection (schema change from unnamed to named
  vectors) — re-ingest is required once after upgrading.
- Slightly higher ingest cost (two embedding passes) — negligible at this
  corpus size; at scale the sparse pass is cheap relative to dense.
