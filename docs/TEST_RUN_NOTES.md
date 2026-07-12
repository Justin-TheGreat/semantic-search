# Live test run — 2026-07-12

A real end-to-end run of the RAGShip capstone on this machine (Windows 11,
Docker Desktop 29.5.2, WSL2 Ubuntu-24.04, NVIDIA RTX 3060 12GB, driver
595.61/CUDA 13.2). Four real bugs were found and fixed. This doc records what
broke, why, and how it was confirmed fixed — see commit `40f7210` for the
actual diffs and [ADR 0005](adr/0005-pin-vllm-version.md) /
[ADR 0006](adr/0006-k8s-service-env-collision.md) for two of them in more
depth.

## What failed

### 1. Docker build: stale base image digest
`docker compose up -d --build` failed immediately:
```
python:3.11-slim-bookworm@sha256:6e61454355...: not found
```
The digest pinned in the Dockerfile (present since the repo's first commit)
no longer resolves on Docker Hub — the tag has since been repushed to a new
digest. **Fixed** by re-pinning to the current digest
(`sha256:f5cf0344c9886ff24d34797578d5d7dd6e8911ae0fe5962bb55d0f89603ec361`).
Digest pins need periodic refresh; they aren't "pin once, forget forever."

### 2. Dockerfile `test` stage was broken since the very first commit
Building `--target test` (the stage that runs pytest inside Docker) failed:
```
ERROR: Could not open requirements file: [Errno 2] No such file or directory: 'requirements.txt'
```
The stage copies `requirements-dev.txt` (which starts with `-r
requirements.txt`) into `/app` but never copies `requirements.txt` itself into
that stage — only the `builder` stage has it, in a different directory. This
bug predates the capstone work (confirmed via `git show` against the initial
commit) and was never caught because `docker compose build` only ever builds
the `runtime` target. **Fixed** by copying both requirement files together.
Verified: `docker build --target test` now runs all 9 pytest tests, all pass.

### 3. `vllm/vllm-openai:latest` crashes under WSL2 GPU passthrough
```
RuntimeError: UVA is not available
```
`:latest` resolved to vLLM 0.25.0. Its newer V2 GPU model runner requires CUDA
Unified Virtual Addressing, which Docker Desktop's WSL2 GPU passthrough layer
doesn't expose. Reproduced identically via `docker compose` and a bare
`docker run`; `VLLM_USE_V1=0` had no effect (not a recognized env var in this
release). **Fixed** by pinning `vllm/vllm-openai:v0.7.3` (last release on the
V0 engine). Verified: model loads, KV cache computes, CUDA graphs capture,
`/v1/chat/completions` returns real completions, and the full `/chat` SSE
pipeline + `eval --with-llm` (score 0.900) ran clean against it.

### 4. Kubernetes: `QDRANT_PORT`/`REDIS_PORT` env collision crash-loops the pod
After a clean `terraform apply` + `kind load docker-image`, the `ragship` pod
crash-looped:
```
pydantic_core._pydantic_core.ValidationError: 2 validation errors for Settings
qdrant_port
  Input should be a valid integer, unable to parse string as an integer
  [input_value='tcp://10.96.122.173:6333', ...]
redis_port
  ... [input_value='tcp://10.96.36.171:6379', ...]
```
Kubernetes auto-injects legacy Docker-links-style env vars
(`<SVCNAME>_PORT=tcp://<ip>:<port>`) for every Service already in the
namespace. The Qdrant and Redis Services are literally named `qdrant` and
`redis`, so `QDRANT_PORT`/`REDIS_PORT` got injected and collided with
`Settings.qdrant_port`/`redis_port` (pydantic-settings binds env vars to
field names case-insensitively). The Postgres Service is named `postgresql`,
not `db`, so `db_port` was untouched by coincidence, not design. This never
shows up in `docker compose` — only real Kubernetes injects these. **Fixed**
by explicitly pinning `QDRANT_PORT`/`DB_PORT`/`REDIS_PORT` in the Helm chart's
deployment env, which takes precedence over the auto-injected vars. Verified:
pod goes `1/1 Running`, `/health`+`/ready` return 200, ingest and `/search`
work through the cluster.

## What worked, no changes needed

- `docker compose build/up -d` (after fix #1) — all 5 core services healthy
- `/health`, `/ready`
- `python -m src.ingest` — chunking + dual dense/sparse embedding + Qdrant
  upsert + Postgres metadata insert
- `/search` — hybrid (RRF-fused dense+sparse) + cross-encoder reranking,
  correctly reorders results (e.g. "Kubernetes" ranks above "Docker" for
  "container orchestration")
- vLLM GPU serving (after fix #3) — confirmed on GPU via `nvidia-smi` and a
  real chat completion
- `/chat` — full LangGraph agent (retrieve → grade_docs → generate → verify)
  streamed via SSE through nginx, grounded + cited + verified answer
- Semantic cache — repeat question returns instantly with `cached: true`
- `eval/run_eval.py` — retrieval-only score 1.000 (CI mode); full mode with
  real LLM generation/citation grading score 0.900 (both well above the 0.8
  CI gate threshold)
- Dockerfile `test` stage (after fix #2) — 9/9 pytest pass
- `docker compose config --quiet` — valid
- Monitoring profile — Prometheus scrapes both `semantic-search` and `vllm`
  targets UP; Grafana auto-provisions the RAGShip dashboard and datasource;
  confirmed `chat_requests_total{cached=...}` metrics match real request
  counts
- `terraform init` / `apply` / `destroy` (after fix #4) — 9 resources
  created/destroyed cleanly; kind cluster, namespace, secret, Postgres/Redis
  Deployments+Services, Qdrant Helm release, app Helm release
- `kind load docker-image` — image side-loads and the pod pulls it
- Ingest and `/search` through the live cluster (via the NodePort → host
  port 8080 mapping)

## One operational note (not a bug)

Running the kind cluster, the full compose stack, vLLM on GPU, and
Prometheus/Grafana **all simultaneously** overloaded this machine badly
enough that in-pod DNS resolution to huggingface.co timed out and the
`ragship` pod failed its liveness probe (`context deadline exceeded`) and got
restarted by kubelet. Stopping the compose `gpu` and `monitoring` profiles
before doing Kubernetes work resolved it immediately — confirmed the DNS
failure was pure host contention, not a CNI/network-policy issue, by
re-running a clean DNS lookup from a fresh pod afterward (it worked
immediately). **Recommendation:** don't run the compose GPU/monitoring
profiles and the kind cluster at the same time on one consumer GPU/machine —
this is now called out in [docs/HOW_TO_RUN.md](HOW_TO_RUN.md).

## Toolchain actually used

See [capstone/TOOLS.txt](../capstone/TOOLS.txt) for exact verified versions
(kind 0.32.0, Helm 4.2.3 — note: newer major than the `>=3.14` the runbook
assumed, worked fine — Terraform 1.15.8).
