# AI Infrastructure Capstone — "RAGShip"

**From your Semantic Search Engine to a production, GPU-served, observable, IaC-provisioned Agentic RAG platform.**

---

## At a glance

| | |
|---|---|
| **Owner** | Justin — Data Engineer → AI Infrastructure Engineer |
| **Builds on** | `semantic-search` repo (FastAPI · sentence-transformers/all-MiniLM-L6-v2 · Qdrant · PostgreSQL · Redis · nginx), on a new branch: `capstone/ragship` |
| **Machine** | Windows 11 · WSL2 (Ubuntu-24.04) · Docker Desktop · NVIDIA GPU — everything runs locally |
| **Cost** | $0 — all OSS + local GPU; no cloud spend |
| **Time budget** | 8–12 hours (one weekend). Phases 0–8 = core; Phase 9 = polish + stretch |
| **Model** | Qwen2.5-0.5B-Instruct served on your GPU via vLLM (OpenAI-compatible) |

### What you'll build

You evolve the search service into an agentic RAG platform. The FastAPI gateway gains a streaming `/chat` endpoint backed by a LangGraph agent (retrieve → grade → generate → verify). Retrieval upgrades from pure-dense to hybrid (dense+sparse) with a cross-encoder reranker. A real LLM runs on your GPU via vLLM. The whole stack is provisioned onto a local Kubernetes (kind) cluster by Terraform, watched by Prometheus + Grafana + Langfuse, and gated by a GitHub Actions pipeline that fails the build if RAG quality drops.

### Starting point (your real repo)

`src/main.py` (`/health`, `/search` POST, `/metrics`) · `src/search.py` (Qdrant 384-dim cosine → Postgres metadata → Redis cache) · `src/ingest.py` · 3-stage `Dockerfile` (builder/test/runtime, non-root, pinned digest) · `docker-compose.yaml` (api, db, redis, qdrant, nginx TLS; monitoring profile stubbed) · Docker secrets · **`.github/` is EMPTY** (no CI yet — Phase 8 adds the first workflow).

### Why one capstone (not 21)

You batch capstones at the end of the roadmap and extend the same evolving system. AI-infra hiring tests integration — whether you can make these pieces work together — so a single cumulative platform is the strongest portfolio artifact.

### Phase index

| Phase | Focus | Time | Skills exercised |
|---|---|---|---|
| Phase 0 | Environment & GPU bring-up | ~1.0h | Linux · Networking · GPU basics · Docker |
| Phase 1 | Repo refactor to services | ~1.5h | Python · FastAPI · System design |
| Phase 2 | vLLM GPU serving | ~1.5h | vLLM/KubeRay · GPU infra · Model serving |
| Phase 3 | Hybrid retrieval & reranking | ~1.5h | Vector DBs · Feature pipelines |
| Phase 4 | Agentic RAG with LangGraph | ~2.0h | LangGraph · LLMOps |
| Phase 5 | LLMOps (prompts, cache, eval) | ~1.5h | LLM ops · Model registry · MLflow |
| Phase 6 | Observability | ~1.5h | Prometheus · Grafana · OTel · Langfuse |
| Phase 7 | Kubernetes + Terraform IaC | ~2.0h | Terraform · Networking · Service mesh* |
| Phase 8 | CI/CD with GitHub Actions | ~1.5h | CI/CD for ML · Docker |
| Phase 9 | Load test, docs & design review | ~1.0h | System design · integration |

*Service mesh (Cilium) and MLflow/KubeRay are marked stretch — do them only if time remains.*

> **Format note:** this runbook approximates a standard phase-runbook layout; the original Docker capstone workbook was not in the project folder. Share it and this can be realigned to match exactly.

---

## Skills → Phases Map (all 21 roadmap skills)

Every skill in the roadmap maps to a concrete artifact you build. "Foundational" = used throughout.

| # | Skill | Phase(s) | Concrete artifact you build |
|---|---|---|---|
| 1 | FastAPI ✅ | 1, 4 | Streaming `/chat` (SSE) + `/ready` probe added to the existing gateway |
| 2 | Python for infrastructure | 1, 5 | `src/rag/` package, config, eval harness, prompt registry |
| 3 | Linux systems fundamentals | 0, 7 | WSL2 GPU bring-up, container runtime, kind nodes |
| 4 | Networking fundamentals | 0, 6, 7 | k8s Services/probes, ExternalName to host GPU, TLS via nginx |
| 5 | System design | 1, 9 | Service decomposition, ADRs, design-review answers |
| 6 | Vector databases (beyond Qdrant) | 3 | Named dense+sparse vectors, hybrid Query API + RRF fusion |
| 7 | ML feature pipelines | 3 | Chunking + dual-embedding ingestion pipeline |
| 8 | ML model serving | 2 | vLLM OpenAI-compatible serving on GPU |
| 9 | vLLM / KubeRay | 2, 7 | GPU vLLM container; (stretch) KubeRay RayService |
| 10 | GPU infrastructure basics | 0, 2 | NVIDIA Container Toolkit, VRAM budgeting, `--gpus all` |
| 11 | LangGraph | 4 | retrieve→grade→generate→verify stateful agent graph |
| 12 | LLM operationalization | 5 | Prompt versioning, semantic cache, guardrails, token/cost metrics |
| 13 | Model registries & versioning | 5 | Versioned prompts + model registry entry (stretch: MLflow) |
| 14 | MLflow / experiment tracking | 5 | Eval runs logged (score, params) to self-hosted MLflow |
| 15 | Observability (Prom/Grafana/OTel/Langfuse) | 6 | Grafana dashboard, Langfuse traces, OTel spans, alert rule |
| 16 | CI/CD for ML pipelines | 8 | GitHub Actions: lint/test/scan + eval-quality gate + registry push |
| 17 | Terraform / IaC | 7 | kind cluster + Helm releases + app, all from `terraform apply` |
| 18 | Service mesh (Istio / Cilium) | 7* | Cilium CNI + default-deny NetworkPolicy (stretch) |
| 19 | ML training & evaluation fundamentals | 5 | Golden eval set + retrieval/answer/citation scoring |
| 20 | Feature stores | 3* | Qdrant-as-feature-store pattern for embeddings (noted/stretch) |
| 21 | Fine-tuning & RLHF | 9* | Out of weekend scope — noted as a future extension |

*\* stretch / noted only. The weekend core (phases 0–8) exercises 18 of 21 skills hands-on.*

---

## Phase 0 · Environment & GPU bring-up

**Goal:** prove the GPU + local-Kubernetes toolchain works before writing any code.
**Est. time:** ~1.0 hour · **Skills:** Linux systems · Networking · GPU infrastructure basics · Docker
**Prereq:** Docker Desktop running with WSL2 integration + GPU enabled.
**Deliverable:** a verified local platform toolchain; `capstone/ragship` branch created.

| # | Task | Command / Code | What it does & why | Expected result |
|---|---|---|---|---|
| 1 | Create the capstone branch | `cd path/to/semantic-search`<br>`git checkout -b capstone/ragship` | Isolate all capstone work from `main` so history stays reviewable — a portfolio signal recruiters check. | `git status` shows *On branch capstone/ragship*. |
| 2 | Verify GPU inside WSL2 | `wsl -d Ubuntu-24.04`<br>`nvidia-smi` | CUDA in WSL is driver-only (installed on Windows). This proves the driver is visible in Linux — the substrate vLLM needs. | A table listing your GPU, driver, and CUDA version. |
| 3 | Verify Docker GPU passthrough | `docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi` | Confirms Docker Desktop can schedule the GPU into a container — exactly how Phase 2 runs vLLM. Builds on your Docker skills. | Same `nvidia-smi` table, now printed from inside the container. |
| 4 | Install kind + kubectl | `winget install Kubernetes.kind Kubernetes.kubectl` | kind = Kubernetes-in-Docker: a free, local, throwaway cluster. kubectl talks to it. Needed from Phase 7. | `kind version` and `kubectl version --client` both print. |
| 5 | Install Helm | `winget install Helm.Helm` | Helm packages k8s apps (Postgres/Redis/Qdrant charts) you'll deploy declaratively via Terraform. | `helm version` prints v3.x. |
| 6 | Install Terraform | `winget install Hashicorp.Terraform` | IaC tool that provisions the entire stack in Phase 7 from code — the reproducibility hiring managers look for. | `terraform -version` prints ≥ 1.7. |
| 7 | Pin the toolchain | `printf 'kind 0.x\nkubectl 1.x\nhelm 3.x\nterraform 1.x\n' > capstone/TOOLS.txt` | Documented, pinned tool versions = reproducible environment. Small touch, senior signal. | `TOOLS.txt` committed on the branch. |

**✅ Definition of Done:** `nvidia-smi` succeeds from inside a container; kind, kubectl, helm, and terraform are all runnable; `capstone/ragship` branch exists.

**⚠ Troubleshooting**

- *nvidia-smi works on Windows but fails in WSL* → Update the NVIDIA Windows driver; do NOT install a Linux GPU driver inside WSL — WSL uses the Windows driver via `/usr/lib/wsl`.
- *`--gpus all` → "could not select device driver"* → Enable GPU support in Docker Desktop → Settings → Resources, and ensure WSL integration is on for your distro.
- *kind create later fails on ports 80/443* → Stop the running docker-compose nginx (it binds 443) before Phase 7, or remap kind's host ports.

---

## Phase 1 · Repo refactor to services

**Goal:** reshape the repo for an agent + serving tiers, without breaking the working baseline.
**Est. time:** ~1.5 hours · **Skills:** Python for infrastructure · FastAPI · System design · Docker
**Prereq:** Phase 0 complete; compose baseline currently serves `/health` over TLS.
**Deliverable:** refactored, ruff-clean service layout; baseline still healthy.

| # | Task | Command / Code | What it does & why | Expected result |
|---|---|---|---|---|
| 1 | Fix and harden main.py | Remove the duplicate `/search` and the route defined before `app` exists; keep ONE app, add a readiness probe:<br>`@app.get('/ready')`<br>`async def ready(): return {'ready': service is not None}` | Your current `main.py` has a stray `/metrics` + `/search` defined before `app` is created. A clean liveness (`/health`) vs readiness (`/ready`) split is required for Kubernetes probes in Phase 7. | `curl /health` and `/ready` both return 200 with the app running. |
| 2 | Create the rag package | `mkdir -p src/rag`<br>`touch src/rag/__init__.py src/rag/retriever.py src/rag/reranker.py src/rag/generator.py src/rag/graph.py` | Separates retrieval/reranking/generation/orchestration into modules — mirrors how real ML platform code is organized and keeps `search.py` focused. | New modules import without error. |
| 3 | Add pyproject + ruff | `# pyproject.toml`<br>`[tool.ruff]`<br>`line-length = 100`<br>`[tool.pytest.ini_options]`<br>`pythonpath = ['.']` | One source of truth for lint/test config; matches the lint/test rigor from your Docker lessons (the Dockerfile already runs pytest in a stage). | `ruff check src` passes; pytest still collects tests. |
| 4 | Extend settings | `# src/config.py additions to Settings:`<br>`vllm_base_url: str = 'http://vllm:8000/v1'`<br>`vllm_model: str = 'Qwen/Qwen2.5-0.5B-Instruct'`<br>`reranker_model: str = 'cross-encoder/ms-marco-MiniLM-L-6-v2'`<br>`enable_hybrid: bool = True` | 12-factor config: every new endpoint/model is env-driven, no hardcoded hosts. Consistent with your `get_secret()`/`Settings` pattern. | `from src.config import settings` works with the new fields. |
| 5 | Prove the baseline still works | `docker compose build`<br>`docker compose up -d`<br>`curl -k https://localhost/health` | Regression gate: never advance on a broken baseline. You know this compose stack cold — this is your safety net. | `{'status':'ok','model_loaded':true}` |
| 6 | Checkpoint commit | `git add -A`<br>`git commit -m 'refactor: rag package, probes, tooling'` | Atomic, message-driven commits make the project readable in a portfolio review. | Commit appears in `git log`. |

**✅ Definition of Done:** clean `main.py` with `/health` + `/ready`; `src/rag/` package present; ruff clean; compose still serves `/health` over TLS; work committed.

**⚠ Troubleshooting**

- *Import errors after adding modules* → Ensure `src/rag/__init__.py` exists and `PYTHONPATH=/app` (already set in your Dockerfile runtime stage).
- *ruff flags many pre-existing issues* → Scope the gate: `ruff check src/rag` first, then widen. Don't rewrite working code you won't touch this weekend.

---

## Phase 2 · vLLM GPU serving

**Goal:** serve a real LLM on your GPU with an OpenAI-compatible API.
**Est. time:** ~1.5 hours · **Skills:** vLLM/KubeRay · GPU infrastructure · ML model serving
**Prereq:** Phase 0 GPU passthrough verified.
**Deliverable:** GPU-backed `/v1/chat/completions` endpoint, wired into compose behind a profile.

| # | Task | Command / Code | What it does & why | Expected result |
|---|---|---|---|---|
| 1 | Pick a small instruct model | `MODEL=Qwen/Qwen2.5-0.5B-Instruct` | 0.5B params fit comfortably in consumer VRAM and run free locally — matches your GPU-lab note (small models like Qwen2.5-0.5B / TinyLlama). | Model id chosen; no download needed yet (vLLM pulls it). |
| 2 | Run vLLM on the GPU | `docker run --gpus all -p 8001:8000 --ipc=host vllm/vllm-openai:latest --model Qwen/Qwen2.5-0.5B-Instruct --max-model-len 4096 --gpu-memory-utilization 0.85` | Starts an OpenAI-compatible server on the real GPU. `--ipc=host` avoids CUDA shared-memory errors; `--max-model-len` caps the KV cache to fit VRAM. | Logs show weights loaded on GPU and *Uvicorn running on 0.0.0.0:8000*. |
| 3 | Confirm it's really on the GPU | `nvidia-smi` | Verifies weights occupy VRAM (not silent CPU fallback). GPU-infra fluency = knowing how to check utilization. | A python process listed under the GPU with VRAM allocated. |
| 4 | Smoke-test the API | `curl http://localhost:8001/v1/chat/completions -H 'Content-Type: application/json' -d '{"model":"Qwen/Qwen2.5-0.5B-Instruct","messages":[{"role":"user","content":"Say hi in 5 words"}]}'` | Proves the generation tier works standalone before you wire RAG into it — isolate failures early. | JSON response with a `choices[0].message.content` completion. |
| 5 | Add vLLM to compose (gpu profile) | `vllm:`<br>`  image: vllm/vllm-openai:latest`<br>`  profiles: [gpu]`<br>`  command: --model Qwen/Qwen2.5-0.5B-Instruct --max-model-len 4096`<br>`  deploy: { resources: { reservations: { devices: [{ driver: nvidia, count: 1, capabilities: [gpu] }] } } }` | Makes GPU serving part of the reproducible stack. Docker connection: the same compose you mastered, now GPU-aware via device reservations + profiles. | `docker compose --profile gpu up vllm` starts and loads the model. |
| 6 | Parameterize the base URL | compose: `VLLM_BASE_URL=http://vllm:8000/v1`<br>kind (Phase 7): `http://host.docker.internal:8001/v1` | Decouples the app from where the model runs, so the same code works in compose and in the cluster. | `settings.vllm_base_url` resolves in both contexts. |

**✅ Definition of Done:** an OpenAI-compatible endpoint on the GPU returns chat completions, and vLLM is reproducible via `docker compose --profile gpu up`.

**⚠ Troubleshooting**

- *CUDA out of memory / KV cache won't allocate* → Lower `--max-model-len` (e.g. 2048) or `--gpu-memory-utilization` (0.7). Close other GPU apps.
- *RuntimeError about shared memory* → Add `--ipc=host` (or `--shm-size=1g`) to the docker run.
- *Very slow first request* → First call compiles CUDA graphs + downloads weights; subsequent calls are fast. Pre-warm with one dummy request.

---

## Phase 3 · Hybrid retrieval & reranking

**Goal:** upgrade retrieval from pure-dense to hybrid + cross-encoder reranking.
**Est. time:** ~1.5 hours · **Skills:** Vector databases (beyond Qdrant) · ML feature pipelines
**Prereq:** Qdrant running (compose); existing dense ingest works.
**Deliverable:** hybrid + reranked `/search` that measurably reorders results vs dense-only.

| # | Task | Command / Code | What it does & why | Expected result |
|---|---|---|---|---|
| 1 | Add sparse embeddings | `pip install fastembed`  *(add to requirements.txt)* | FastEmbed provides BM25/SPLADE sparse vectors so search combines keyword precision with semantic recall — the core of hybrid retrieval. | `fastembed` imports; requirements updated. |
| 2 | Recreate the collection with named vectors | `client.create_collection('articles',`<br>`  vectors_config={'dense': VectorParams(size=384, distance=Distance.COSINE)},`<br>`  sparse_vectors_config={'sparse': SparseVectorParams()})` | Hybrid search needs both vector types under one collection. Keeps your existing 384-dim dense model; adds a sparse channel. | Qdrant collection info shows a dense and a sparse vector. |
| 3 | Chunk article bodies | `# src/ingest.py: split body into ~512-token windows, 64-token overlap; one point per chunk`<br>`chunks = chunk(a['body'], size=512, overlap=64)` | Chunk-level granularity retrieves far better than whole-document for RAG — the model sees focused, relevant passages. | Re-ingest logs a chunk count greater than the article count. |
| 4 | Implement the hybrid query | `client.query_points('articles',`<br>`  prefetch=[Prefetch(query=dense_vec, using='dense', limit=50),`<br>`            Prefetch(query=sparse_vec, using='sparse', limit=50)],`<br>`  query=FusionQuery(fusion=Fusion.RRF), limit=50)` | Reciprocal Rank Fusion merges dense + sparse result lists — the modern, robust Qdrant hybrid pattern. | Retriever returns a fused candidate list of ~50 hits. |
| 5 | Add a cross-encoder reranker | `from sentence_transformers import CrossEncoder`<br>`ce = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')`<br>`# score (query, passage) pairs; keep top 8` | A second, precise ranking stage over the top-50 → top-8. Two-stage retrieve→rerank is the standard production RAG shape. Runs fine on CPU. | Reranked top-8 order differs from raw fusion order. |
| 6 | Feature-flag /search | `if settings.enable_hybrid:`<br>`    hits = rerank(hybrid_search(q))[:limit]`<br>`else:`<br>`    hits = dense_search(q, limit)` | Lets you A/B the old vs new retrieval and roll back instantly — safe rollout discipline. | `/search` returns better-ranked hits with `enable_hybrid=true`. |
| 7 | Re-ingest and sanity-check | `docker compose exec api python -m src.ingest`<br>`curl -k -X POST https://localhost/search -d '{"query":"neural network training","limit":5}'` | Rebuild the index with chunks + sparse vectors, then confirm a keyword-heavy query surfaces the right passages. | Hybrid results beat pure-dense on a keyword-specific query. |

**✅ Definition of Done:** hybrid (dense+sparse) retrieval with cross-encoder reranking is live behind a flag and demonstrably reorders results vs dense-only.

**⚠ Troubleshooting**

- *Sparse vector errors on upsert* → Ensure you pass sparse indices/values in the `SparseVector` format and reference the correct vector name (`'sparse'`).
- *Reranker slow* → Batch the (query, passage) pairs into one `ce.predict()` call; cap candidates to 50.

---

## Phase 4 · Agentic RAG with LangGraph

**Goal:** orchestrate retrieve → grade → generate → verify as a stateful graph on your GPU model.
**Est. time:** ~2.0 hours · **Skills:** LangGraph · LLM operationalization (intro)
**Prereq:** Phases 2 (vLLM) and 3 (retriever) complete.
**Deliverable:** `/chat` streams grounded, cited answers via a self-correcting graph.

| # | Task | Command / Code | What it does & why | Expected result |
|---|---|---|---|---|
| 1 | Install LangGraph + client | `pip install langgraph langchain-openai langchain-core`  *(add to requirements.txt)* | LangGraph gives you an explicit, debuggable agent state machine; langchain-openai is the OpenAI-compatible client pointed at vLLM. | Imports succeed. |
| 2 | Define graph state | `class RAGState(TypedDict):`<br>`    question: str; docs: list; grade: str`<br>`    answer: str; citations: list; attempts: int` | Explicit typed state is what makes an agent observable and testable — you can log/trace every field between nodes. | Module imports; state schema defined. |
| 3 | Node — retrieve | `def retrieve(s): s['docs'] = hybrid_rerank(s['question']); return s` | Pulls hybrid+reranked context (Phase 3) into state. | `docs` populated in state. |
| 4 | Node — grade_docs (self-correct) | `# LLM grades relevance; if weak and attempts<2, rewrite query and loop back to retrieve`<br>`edge: grade=='no' -> retrieve ; else -> generate` | Corrective RAG: the agent refuses to answer from junk context and retries with a better query — a real production quality guard. | Conditional edge loops on a bad first retrieval. |
| 5 | Node — generate | `llm = ChatOpenAI(base_url=settings.vllm_base_url, api_key='x', model=settings.vllm_model)`<br>`# answer ONLY from graded docs; return citations` | Grounded generation on your local GPU model ($0), with source attribution — the anti-hallucination baseline. | `answer` + `citations` in state. |
| 6 | Node — verify | `# check every claim is supported by docs; if not and attempts<2 -> regenerate` | Hallucination guard: production RAG must validate the answer against sources before returning it. | verify passes, or loops once, then returns best-effort with a low-confidence flag. |
| 7 | Compile + expose /chat (SSE) | `graph = builder.compile()`<br>`@app.post('/chat')`<br>`async def chat(req):`<br>`    return StreamingResponse(stream_graph(req.query), media_type='text/event-stream')` | A user-facing streaming endpoint — tokens arrive live. Extends your FastAPI gateway you already know well. | `curl -N .../chat` streams tokens for a question. |
| 8 | End-to-end test | `curl -N -k -X POST https://localhost/chat -d '{"query":"How does machine learning differ from AI?"}'` | Confirms the full path: retrieve → grade → generate → verify → stream, all on local infra. | A streamed, grounded answer with citations to article ids. |

**✅ Definition of Done:** `/chat` runs the four-node graph against your GPU model and returns grounded, cited answers, self-correcting on weak retrieval.

**⚠ Troubleshooting**

- *LangChain can't reach vLLM* → `base_url` must end in `/v1` and point to the reachable host (`vllm:8000` in compose, `host.docker.internal:8001` from kind). `api_key` can be any non-empty string.
- *Graph loops forever* → Cap `attempts` (e.g. < 2) in the conditional edges and always have a terminal path to generate/return.

---

## Phase 5 · LLMOps — prompts, cache, eval

**Goal:** make the agent operable — versioned prompts, semantic caching, guardrails, and a quality score.
**Est. time:** ~1.5 hours · **Skills:** LLM operationalization · Model registries (intro) · MLflow (intro) · ML evaluation
**Prereq:** Phase 4 graph works.
**Deliverable:** `python -m eval.run_eval` prints a score and writes `eval/report.json`.

| # | Task | Command / Code | What it does & why | Expected result |
|---|---|---|---|---|
| 1 | Version your prompts | `# src/rag/prompts/ -> grade_v1.txt, generate_v1.txt ...`<br>`PROMPTS = {'generate': {'v1': ..., 'v2': ...}}`<br>`ACTIVE = {'generate': 'v2'}` | Treat prompts as versioned artifacts you can A/B and roll back — the foundation of prompt ops and reproducibility. | Response metadata records which prompt version served it. |
| 2 | Add an LLM semantic cache | `# extend Redis: key on prompt embedding; if cosine-sim to a cached prompt > 0.97, reuse answer` | Cuts latency and GPU cost on repeated/similar questions — reuses the Redis you already run for search caching. | A repeated question is served from cache (`cached=true`). |
| 3 | Token & cost metrics | `# src/metrics.py`<br>`prompt_tokens = Counter('llm_prompt_tokens_total', ...)`<br>`completion_tokens = Counter('llm_completion_tokens_total', ...)`<br>`node_latency = Histogram('graph_node_seconds', 'per-node', ['node'])` | These are the numbers an AI-infra team watches daily. Extends your existing Prometheus `/metrics` endpoint. | New series appear at `/metrics`. |
| 4 | Add guardrails | `# input: reject query > 500 chars (422)`<br>`# output: max_tokens cap; refuse if no graded docs` | Basic safety + cost controls that keep the service predictable under abuse or empty retrieval. | Oversized input returns 422; empty-context returns a safe refusal. |
| 5 | Build the golden eval set | `# eval/golden.jsonl  (~20 lines)`<br>`{"q":"...","must_include":["..."],"must_cite":["a001"]}` | An objective, versioned quality bar — the exact thing the CI gate in Phase 8 enforces. | `eval/golden.jsonl` with ~20 labeled cases. |
| 6 | Write the eval harness | `# eval/run_eval.py -> per case: retrieval hit-rate, answer keyword-match, citation accuracy; mean score`<br>`python -m eval.run_eval` | Reproducible quality measurement (an MLflow-style run) that turns "seems good" into a number you can gate on. | Prints an overall score and writes `eval/report.json`. |
| 7 | (Optional) Log to MLflow | `docker run -p 5000:5000 ghcr.io/mlflow/mlflow mlflow server`<br>`mlflow.log_metric('rag_score', score)` | Experiment tracking + prompt/model versioning — register which prompt+model produced which score. | Run visible in the MLflow UI at `:5000`. |

**✅ Definition of Done:** prompts are versioned, an LLM semantic cache is active, token/cost/latency metrics are exported, and the eval harness produces a gated score + JSON report.

**⚠ Troubleshooting**

- *Eval score is 0* → Check the retriever returns docs for the golden questions and that `must_cite` ids exist in your ingested data.
- *Semantic cache never hits* → Lower the similarity threshold slightly (0.95) and confirm you embed the normalized prompt, not the raw request JSON.

---

## Phase 6 · Observability

**Goal:** see the system — metrics, dashboards, and per-node LLM traces.
**Est. time:** ~1.5 hours · **Skills:** Observability: Prometheus · Grafana · OpenTelemetry · Langfuse
**Prereq:** Phase 5 metrics exported.
**Deliverable:** live Grafana RAG+GPU dashboard and Langfuse graph traces.

| # | Task | Command / Code | What it does & why | Expected result |
|---|---|---|---|---|
| 1 | Activate the monitoring profile | `# fix compose: put prometheus + grafana UNDER services: (they're currently mis-indented at root) then:`<br>`docker compose --profile monitoring up -d` | Your compose already stubs Prometheus+Grafana but the block is mis-indented at the root level — fixing it turns monitoring on. | prometheus and grafana containers start. |
| 2 | Confirm the scrape | `# monitoring/prometheus.yml already targets api:8000/metrics`<br>`# open http://localhost:9090/targets` | Prometheus is already pointed at your API — now it collects the RAG/token/latency metrics from Phase 5. | The semantic-search target shows state UP. |
| 3 | Build a Grafana dashboard | `# monitoring/grafana/dashboards/ragship.json`<br>`# panels: p95 /chat latency, tokens/sec, cache-hit %, GPU VRAM, eval score, requests by cached` | One pane of glass an interviewer immediately understands. Provisioned as JSON so it's reproducible, not click-ops. | Dashboard renders with live panels at `http://localhost:3000`. |
| 4 | Add Langfuse tracing | `# self-host: git clone langfuse && docker compose up -d`<br>`from langfuse.decorators import observe`<br>`@observe()`<br>`def generate(s): ...` | Per-node LLM traces (retrieve/grade/generate/verify) with latency, tokens, and prompt/response — the LLM-native complement to Prometheus. Free, self-hosted. | Traces for each `/chat` call appear in the Langfuse UI. |
| 5 | Add OpenTelemetry spans | `pip install opentelemetry-instrumentation-fastapi`<br>`FastAPIInstrumentor.instrument_app(app)` | Distributed tracing across the whole request path (HTTP → graph → retriever → vLLM) — standard, vendor-neutral instrumentation. | Spans are emitted (console exporter or Tempo). |
| 6 | (Bonus) Alert rule | `# prometheus rule: eval_score < 0.8 OR p95 > 2s`<br>`for: 5m -> alert` | Proactive quality + latency alerting — you find regressions before users do. | Rule loads; fires in a forced-failure test. |

**✅ Definition of Done:** Grafana shows live RAG + GPU panels, Prometheus scrapes are UP, and Langfuse displays per-node traces for `/chat`.

**⚠ Troubleshooting**

- *Grafana target DOWN* → Ensure api and prometheus share the backend network and the API actually exposes `/metrics` (test with `curl api:8000/metrics`).
- *Langfuse compose heavy* → It's fine for a weekend on your machine; if RAM-tight, run Langfuse only while demoing, not 24/7.

---

## Phase 7 · Kubernetes + Terraform IaC

**Goal:** provision the whole platform on a local kind cluster from a single `terraform apply`.
**Est. time:** ~2.0 hours · **Skills:** Terraform / IaC · Networking · Service mesh (stretch)
**Prereq:** Phases 1–6; images buildable; kind/helm/terraform installed.
**Deliverable:** `terraform apply` stands up the full platform; `/chat` works through the cluster.

| # | Task | Command / Code | What it does & why | Expected result |
|---|---|---|---|---|
| 1 | Terraform skeleton | `# infra/terraform/main.tf`<br>`terraform { required_providers {`<br>`  kind = { source = 'tehcyx/kind' }`<br>`  helm = { source = 'hashicorp/helm' }`<br>`  kubernetes = { source = 'hashicorp/kubernetes' } } }` | Declarative provisioning of the cluster AND the releases from one codebase — the reproducibility that defines IaC. | `terraform init` succeeds and downloads providers. |
| 2 | Provision the cluster | `resource 'kind_cluster' 'ragship' {`<br>`  name = 'ragship'`<br>`  # extra_port_mappings 80->80, 443->443`<br>`}` | A free, local, reproducible Kubernetes cluster. Port mappings expose the ingress to your host. | `terraform apply` creates it; `kubectl get nodes` shows the node Ready. |
| 3 | Deploy deps via Helm | `resource 'helm_release' 'qdrant' { chart='qdrant' ... }`<br>`# + postgresql + redis (Bitnami charts)` | Infra dependencies deployed declaratively instead of hand-rolled — how real clusters manage stateful services. | qdrant/postgres/redis pods reach Running. |
| 4 | Deploy the app | `# deploy/helm/ragship/ : Deployment + Service + liveness(/health)+readiness(/ready) probes + HPA`<br>`resource 'helm_release' 'ragship' { ... }` | Your API becomes a first-class k8s workload with autoscaling and the probes you added in Phase 1. | `kubectl get svc ragship`; pods Ready. |
| 5 | Reach the host GPU from the cluster | `# ExternalName Service -> host.docker.internal`<br>`apiVersion: v1`<br>`kind: Service`<br>`spec: { type: ExternalName, externalName: host.docker.internal }` | Single-GPU pragmatic pattern: keep vLLM on the host (Phase 2) and let in-cluster pods call it. Documented tradeoff vs in-cluster GPU. | A pod can curl the vLLM endpoint through the ExternalName. |
| 6 | Secrets via Terraform | `resource 'kubernetes_secret' 'db' {`<br>`  data = { password = var.db_password } }`<br>`# var marked sensitive; not committed` | Secure, uncommitted config — mirrors the Docker secrets you already use in compose. | Secret mounted into the app pod. |
| 7 | One-command up / down | `terraform apply     # whole platform`<br>`terraform destroy   # clean teardown` | The entire platform reproducible from code — the headline capability for an AI-infra role. | Full stack comes up from scratch; destroy removes it cleanly. |
| 8 | (Stretch) Cilium + NetworkPolicy | `# install Cilium CNI on kind; default-deny + allow api->qdrant/redis/postgres only` | Zero-trust pod networking — a taste of service mesh / network security. | Cross-pod traffic blocked unless explicitly allowed. |

**✅ Definition of Done:** a single `terraform apply` provisions the kind cluster, Helm deps, and the app; `/chat` works end-to-end through the cluster; `terraform destroy` cleans up.

**⚠ Troubleshooting**

- *kind pods stuck ImagePullBackOff* → Build locally then `kind load docker-image ragship:sha` — kind can't see your local Docker registry by default.
- *GPU inside kind is painful* → Expected on a single consumer GPU. Keep vLLM on the host via ExternalName (documented). True in-cluster GPU/KubeRay is the stretch.
- *host.docker.internal unresolved in pod* → Add it via `hostAliases` or use the Docker Desktop host-gateway IP.

---

## Phase 8 · CI/CD with GitHub Actions

**Goal:** automate quality on every push — including an ML-specific eval gate.
**Est. time:** ~1.5 hours · **Skills:** CI/CD for ML pipelines · Docker (carry-over)
**Prereq:** Phase 5 eval harness; Dockerfile test stage; GHCR access.
**Deliverable:** PRs to main run lint/test/scan/eval-gate/manifest-validate and go red on failure.

| # | Task | Command / Code | What it does & why | Expected result |
|---|---|---|---|---|
| 1 | Create the first workflow | `# .github/workflows/ci.yml  (this dir is currently EMPTY)`<br>`on: [push, pull_request]` | Your semantic-search repo has no CI yet. This is where the Docker-lesson GitHub Actions skill lands on the AI system. | Actions tab shows the workflow running on push. |
| 2 | Lint + test job | `- run: pip install -r requirements-dev.txt`<br>`- run: ruff check src`<br>`- run: pytest tests/ -v` | Fast feedback on every change. Your 3-stage Dockerfile already fails the build if tests fail — CI enforces it before images are built. | Job is green on a clean commit. |
| 3 | Build + security scan | `- uses: docker/build-push-action (target: runtime)`<br>`- run: docker scout cves --exit-code --only-severity critical`<br>`  # or aquasecurity/trivy-action` | Supply-chain gate. Docker Scout is exactly the scanner from your Docker lessons — reused here. | No critical CVEs; build succeeds. |
| 4 | Push to GHCR | `- uses: docker/build-push-action`<br>`  with: { push: true, tags: ghcr.io/<you>/ragship:${{ github.sha }} }` | Versioned image registry (free for public images) — every commit yields a traceable, deployable artifact. | Image appears in GHCR tagged with the commit sha. |
| 5 | **THE eval quality gate** | `- run: python -m eval.run_eval --threshold 0.8`<br>`  # non-zero exit fails the job if score < 0.8` | The ML-specific CD control that separates "ML in a notebook" from "ML in production" — you never merge a quality regression. | A PR that lowers RAG quality is blocked by a red gate. |
| 6 | Validate deploy artifacts | `- run: helm template deploy/helm/ragship \| kubeconform -`<br>`- run: terraform -chdir=infra/terraform validate` | GitHub-hosted runners can't reach your local kind, so CI validates the manifests/IaC; the real deploy stays local via `terraform apply`. Honest, correct CD boundary. | Manifests and Terraform validate clean. |
| 7 | Document branch protection | `# settings: require ci.yml + eval-gate before merge to main` | Process maturity — protected main with required checks is a senior signal. | Merge is blocked until checks pass. |

**✅ Definition of Done:** every PR to main runs lint → test → build+scan → GHCR push → eval gate → manifest/IaC validation, and fails visibly on any regression.

**⚠ Troubleshooting**

- *Eval gate can't load the GPU model in CI* → Point the harness at a tiny CPU model or a mocked LLM for CI; the gate measures retrieval + citation accuracy, which don't need the GPU.
- *GHCR push denied* → Add `permissions: packages: write` and log in with `GITHUB_TOKEN` in the workflow.

---

## Phase 9 · Load test, docs & design review

**Goal:** turn a working system into a portfolio-ready, defensible project.
**Est. time:** ~1.0 hour (+ stretch) · **Skills:** System design · integration · communication
**Prereq:** Phases 0–8 complete.
**Deliverable:** public, portfolio-ready repo: load numbers, diagram, ADRs, v1.0 tag.

| # | Task | Command / Code | What it does & why | Expected result |
|---|---|---|---|---|
| 1 | Load test | `# k6 or locust against /search and /chat`<br>`k6 run load/chat_test.js  # record p50/p95, tokens/s` | Capacity numbers make the project concrete and quantified for your README and interviews. | A results table: p50/p95 latency, throughput, GPU utilization. |
| 2 | Architecture README | `# README.md: embed the architecture diagram, the stack, decisions, and a copy-paste 'run it' section` | The artifact recruiters and hiring managers actually read first. | README renders with the diagram and a working quick-start. |
| 3 | ADR log | `# docs/adr/0001-hybrid-retrieval.md, 0002-host-gpu-vllm.md, 0003-eval-gate.md` | Short Architecture Decision Records show senior-level reasoning about tradeoffs. | 3–4 ADRs committed. |
| 4 | Design-review self-quiz | `# docs/design-review.md — answer the 6 constraint prompts (below)` | Builds the system-design fluency interviewers probe — you can defend every choice. | Written answers to all six prompts. |
| 5 | Portfolio polish | `git tag v1.0 && git push --tags`<br>`# pin the repo; add Grafana/Langfuse screenshots` | Job-application ready: tagged release, visuals, pinned repo. | v1.0 release + screenshots in the repo. |
| 6 | (Stretch) go further | `# MLflow model registry · KubeRay RayService for vLLM · Cilium mTLS · multi-model routing` | Optional depth if you have appetite — each maps to a not-started roadmap skill. | Any one stretch item done and documented. |

**✅ Definition of Done:** the repo is public and portfolio-ready: quantified load numbers, an architecture diagram, ADRs, answered design-review prompts, and a v1.0 tag.

**⚠ Troubleshooting**

- *Load test saturates the GPU instantly* → 0.5B on one consumer GPU has modest throughput — report honest numbers and note the batching/quantization levers you'd pull to scale.
- *Running low on the weekend budget* → Ship phases 0–8 + README + tag; move ADRs/stretch to a follow-up. A working, documented core beats an unfinished sprawl.

---

## Definition of Done & Portfolio Checklist

### Per-phase Definition of Done

- [ ] **Phase 0** — nvidia-smi runs in a container; kind/kubectl/helm/terraform installed; branch created.
- [ ] **Phase 1** — clean `/health` + `/ready`; `src/rag/` package; ruff clean; compose baseline healthy.
- [ ] **Phase 2** — GPU vLLM returns OpenAI-compatible completions; reproducible via compose profile.
- [ ] **Phase 3** — hybrid + reranked retrieval reorders results vs dense-only.
- [ ] **Phase 4** — `/chat` streams grounded, cited answers via the retrieve→grade→generate→verify graph.
- [ ] **Phase 5** — versioned prompts, semantic cache, token/cost metrics, eval harness with a score.
- [ ] **Phase 6** — Grafana RAG+GPU dashboard live; Langfuse per-node traces visible.
- [ ] **Phase 7** — one `terraform apply` provisions the whole platform on kind; `/chat` works via the cluster.
- [ ] **Phase 8** — CI runs lint/test/scan/eval-gate/validate; regressions go red.
- [ ] **Phase 9** — load numbers, README+diagram, ADRs, design-review answers, v1.0 tag.

### Skills demonstrated (interview talking points)

- [ ] Provision reproducible infra from code (Terraform → kind + Helm).
- [ ] Serve an LLM on real GPU hardware (vLLM, OpenAI-compatible, VRAM budgeting).
- [ ] Build agentic, self-correcting RAG (LangGraph) with hybrid retrieval + reranking.
- [ ] Operate LLMs (prompt versioning, semantic caching, guardrails, token/cost metrics).
- [ ] Gate quality in CI with an objective eval — not just unit tests.
- [ ] Full observability: metrics, dashboards, and distributed/LLM tracing.

### Sample résumé bullets

- Built a self-hosted agentic RAG platform (FastAPI + LangGraph + vLLM on GPU) serving grounded, cited answers with hybrid dense+sparse retrieval and cross-encoder reranking.
- Provisioned the full stack (Kubernetes/kind, Qdrant, Postgres, Redis, monitoring) from a single `terraform apply`; instrumented with Prometheus, Grafana, and Langfuse.
- Shipped a GitHub Actions CI/CD pipeline with an automated RAG-quality eval gate that blocks merges on regression.

### Design-review prompts (answer these to defend the system)

1. Traffic 10×: where's the first bottleneck (GPU? retriever? Postgres?) and your fix?
2. The GPU box dies: how does `/chat` degrade gracefully?
3. A prompt change drops the eval score 8%: how does CI catch it before prod?
4. Qdrant storage corrupts: what's your backup/restore story?
5. Multi-tenant: how do you isolate one customer's documents at retrieval time?
6. Cost: how would you cut GPU spend 50% without wrecking latency?

### The 3 things to show in an interview

1. `terraform apply` bringing the whole platform up from nothing.
2. The Grafana dashboard + a Langfuse trace of one `/chat` call across all four graph nodes.
3. A PR going red because the eval gate caught a deliberate quality regression.

---

*Runbook approximates a standard phase-runbook format; share your original Docker capstone workbook to realign exactly. Built on the real `semantic-search` repo structure scanned locally — GitHub connector not required.*
