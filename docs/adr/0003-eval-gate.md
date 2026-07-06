# ADR 0003 — CI blocks merges on an objective RAG quality score

**Status:** accepted

## Context

Unit tests can't catch RAG regressions: a prompt tweak, a retriever parameter
change, or a model bump can silently degrade answer quality while every test
stays green.

## Decision

- Maintain a versioned **golden set** (`eval/golden.jsonl`, 20 labeled cases:
  question, `must_include` keywords, `must_cite` article ids).
- `python -m eval.run_eval --threshold 0.8` scores retrieval hit-rate and
  context keyword coverage (plus answer/citation accuracy when an LLM is
  reachable via `--with-llm`), writes `eval/report.json`, and exits non-zero
  below threshold.
- CI (`eval-gate` job) spins up real Qdrant/Postgres/Redis service containers,
  ingests the corpus, and runs the harness **retrieval-only** — GitHub runners
  have no GPU, and retrieval + citation quality are what regress most often.

## Consequences

- A PR that lowers retrieval quality goes red before merge — the ML-specific
  CD control that plain pytest can't provide.
- The gate under-tests generation quality in CI (no LLM). Full-mode eval
  (`--with-llm`) runs locally against the GPU before tagging a release.
- The golden set is small and hand-built; growing it is cheap and each
  addition strengthens the gate.
