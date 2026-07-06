# Design review — RAGShip self-quiz

Answers to the six constraint prompts from the capstone runbook.

## 1. Traffic 10×: where's the first bottleneck and your fix?

The GPU. A 0.5B model on one consumer GPU saturates at a handful of concurrent
generations; retrieval (Qdrant + CPU cross-encoder) and Postgres are orders of
magnitude cheaper per request. Evidence: `vllm:num_requests_waiting` climbs in
Grafana while `graph_node_seconds{node="generate"}` p95 explodes and the other
nodes stay flat.

Fixes, in order of leverage: (1) raise the semantic-cache hit rate (lower the
0.97 threshold, normalize harder) — cached answers skip the GPU entirely;
(2) vLLM-side batching headroom: raise `--max-num-seqs`, shrink
`--max-model-len` so the KV cache fits more sequences; (3) quantized or larger-
batch model (AWQ) or a second GPU replica behind a round-robin URL list. The
cross-encoder comes next; it batches, so move it to GPU or trim candidates
from 50 to 20.

## 2. The GPU box dies: how does /chat degrade gracefully?

`/search` is unaffected (no LLM in the path). In `/chat`, grading *fails open*
(retrieval still returns docs), generation raises, and the stream emits an
`{"event": "error"}` frame instead of hanging — the client gets a fast,
explicit failure. Semantic-cache hits keep serving answered questions with
zero GPU. The next step (not built) would be a fallback `retrieval-only`
response mode: return the top reranked passages with citations and a
"generation unavailable" flag — that's a ~20-line change in `astream_chat`.

## 3. A prompt change drops the eval score 8%: how does CI catch it before prod?

Prompts are versioned files; changing one means a commit, and every push/PR
runs the `eval-gate` job: real Qdrant/Postgres/Redis service containers,
corpus ingest, then `python -m eval.run_eval --threshold 0.8`. A drop from
~0.9 to ~0.83 still passes retrieval-only, which is why prompt-affecting
changes should also run `--with-llm` locally (documented in the release
checklist) — retrieval-only catches retriever regressions in CI; the local
full-mode run catches generation regressions before tagging. With branch
protection requiring `eval-gate`, the red check blocks the merge.

## 4. Qdrant storage corrupts: what's your backup/restore story?

The index is a **derived artifact** — the source of truth is
`data/articles.jsonl` + Postgres metadata. Restore = `python -m src.ingest`,
which drops and rebuilds the collection deterministically (same chunker, same
models). That's the honest answer at this scale: re-ingest beats
backup/restore machinery. At real scale: Qdrant snapshots API on a schedule,
shipped to object storage, plus Postgres `pg_dump`; restore drills verified by
running the eval harness against the restored index.

## 5. Multi-tenant: how do you isolate one customer's documents at retrieval time?

Add `tenant_id` to every chunk payload at ingest, and make every Qdrant query
carry a server-side `Filter(must=[FieldCondition(key="tenant_id", match=...)])`
derived from the authenticated principal — never from the request body. Cache
keys (Redis search cache and the semantic cache) must be prefixed with the
tenant id, or one tenant's cached answer leaks to another — the subtle one.
Postgres rows get the same column with row-level security. For hard isolation
(compliance), one Qdrant collection per tenant trades memory for a clean
blast-radius story.

## 6. Cost: how would you cut GPU spend 50% without wrecking latency?

Measure first: tokens/request × requests/day from `llm_*_tokens_total`. Then:
(1) semantic cache aggressiveness — every hit is 100% GPU savings and *better*
latency; (2) prompt diet — the generate prompt carries 8 chunks; eval whether
top-4 holds the score (halves prompt tokens, which dominate at small answer
sizes); (3) cap `max_tokens` tighter and keep answers ≤120 words (already in
the v2 prompt); (4) quantize (AWQ/INT4) — ~2× throughput per GPU at minor
quality cost, verified by the eval harness before rollout; (5) batch window
tuning in vLLM. The eval gate is what makes each lever safe to pull.
