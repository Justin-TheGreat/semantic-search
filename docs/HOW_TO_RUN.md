# How to run RAGShip — step by step

This guide takes you from a fresh machine to the full platform. Follow it top
to bottom the first time; afterwards each section works on its own.
Run all commands from the repo root (`semantic-search/`) in **PowerShell**
unless a step says otherwise.

---

## 0. One-time setup (~15 min)

**a. Start Docker Desktop** and make sure two settings are on
(Settings → Resources → WSL integration, and GPU support):

```powershell
docker info        # should print server info, not an error
```

**b. Verify the GPU is visible to containers** (needs an NVIDIA GPU + current
Windows driver — do NOT install a Linux driver inside WSL):

```powershell
docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi
```

You should see your GPU table printed from inside the container.

**c. Install the Kubernetes/IaC toolchain** (only needed for section 6):

```powershell
winget install Kubernetes.kind Kubernetes.kubectl Helm.Helm Hashicorp.Terraform
```

Close and reopen the terminal, then check: `kind version`, `helm version`,
`terraform -version`. Record your versions in `capstone/TOOLS.txt`.

**d. Create the local secret and TLS cert** (first clone only):

```powershell
"changeme_strong_password" | Out-File -Encoding ascii -NoNewline secrets/db_password.txt
```

For the cert, run in Git Bash or WSL: `bash nginx/generate-certs.sh`

---

## 1. Core stack (API + databases) (~5 min first build)

```powershell
docker compose up -d --build
```

First build downloads Python deps (a few GB, one time). Wait until healthy,
then:

```powershell
curl.exe -k https://localhost/health     # {"status":"ok","model_loaded":true}
curl.exe -k https://localhost/ready      # {"ready":true}
```

The very first start also downloads the embedding models into the
`model-cache` volume — `/health` can take a minute or two to go green.

## 2. Ingest the corpus

```powershell
docker compose exec api python -m src.ingest
```

Expected: "6 articles", a chunk count, dense + sparse encoding, "Done!".
Re-run any time — it rebuilds the index from scratch (that's the
backup/restore story: the index is derived, `data/articles.jsonl` is truth).

## 3. Try hybrid search

```powershell
curl.exe -k -X POST https://localhost/search -H "Content-Type: application/json" -d '{\"query\": \"container orchestration\", \"limit\": 5}'
```

You get reranked hits with scores. To compare against old dense-only behavior:
set `ENABLE_HYBRID=false` on the api service in docker-compose.yaml,
`docker compose up -d api`, repeat the query, then set it back.

## 4. GPU LLM tier (vLLM)

```powershell
docker compose --profile gpu up -d
docker logs -f search-vllm      # wait for "Uvicorn running on 0.0.0.0:8000"
```

First start downloads the Qwen2.5-0.5B weights (~1 GB). Then smoke-test:

```powershell
curl.exe http://localhost:8001/v1/chat/completions -H "Content-Type: application/json" -d '{\"model\": \"Qwen/Qwen2.5-0.5B-Instruct\", \"messages\": [{\"role\": \"user\", \"content\": \"Say hi in 5 words\"}]}'
```

Confirm it's really on the GPU: `nvidia-smi` should show a python process
with VRAM allocated.

## 5. Chat — the agentic RAG endpoint

```powershell
curl.exe -k -N -X POST https://localhost/chat -H "Content-Type: application/json" -d '{\"query\": \"What is Kubernetes used for?\"}'
```

You'll see SSE frames: node events (retrieve → grade_docs → generate →
verify), streamed tokens, then a final `done` frame with `citations`,
`verified`, and `prompt_version`. Ask the same question twice — the second
answer returns instantly with `"cached": true` (semantic cache).

## 6. Monitoring

```powershell
docker compose --profile monitoring up -d
```

- Prometheus: <http://localhost:9090/targets> — `semantic-search` target UP
  (`vllm` is UP only while the gpu profile runs).
- Grafana: <http://localhost:3000> (admin / admin) → dashboard
  **RAGShip — Agentic RAG Platform** (auto-provisioned). Send a few /chat and
  /search requests to make the panels move.
- Alert rules (p95 latency, API down) are in `monitoring/alerts.yml` —
  see Prometheus → Alerts.

Optional — Langfuse LLM traces: self-host per
<https://langfuse.com/self-hosting/docker-compose>, then set
`LANGFUSE_ENABLED=true` plus `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` /
`LANGFUSE_HOST` env vars on the api service and restart it.

## 7. Quality eval (the number CI gates on)

```powershell
# retrieval-only (no GPU needed):
docker compose exec api python -m eval.run_eval --threshold 0.8

# full mode — also grades generated answers + citations (GPU profile must be up):
docker compose exec api python -m eval.run_eval --with-llm
```

Prints a per-case table + overall score and writes `eval/report.json`.
Run `--with-llm` locally before tagging a release (CI can't — no GPU there).

## 8. Kubernetes platform from one command (Terraform + kind)

**Important:** kind and the compose nginx don't conflict (the cluster maps to
host port **8080**), but the api container and cluster share the GPU vLLM —
keep the gpu profile running.

```powershell
cd infra/terraform
terraform init
terraform apply          # type: yes — creates cluster + Qdrant + Postgres + Redis + app
```

Then build and side-load the app image (kind can't see your local Docker
images by default), from the repo root:

```powershell
docker build -t ragship:local --target runtime .
kind load docker-image ragship:local --name ragship
kubectl --context kind-ragship -n ragship get pods    # wait for Running/Ready
```

Ingest inside the cluster and test through it:

```powershell
kubectl --context kind-ragship -n ragship exec deploy/ragship -- python -m src.ingest
curl.exe http://localhost:8080/health
curl.exe -N -X POST http://localhost:8080/chat -H "Content-Type: application/json" -d '{\"query\": \"What is machine learning?\"}'
```

Tear it all down (compose stack is untouched):

```powershell
terraform destroy
```

Custom DB password: `$env:TF_VAR_db_password = "your-password"` before apply.

## 9. CI/CD (GitHub Actions)

Push the branch and open a PR:

```powershell
git push -u origin capstone/ragship
```

The `ci` workflow runs four jobs on every push/PR: **lint-test**,
**eval-gate** (real Qdrant/Postgres/Redis containers, ingest, score ≥ 0.8 or
red), **build-scan-push** (Docker build, Trivy critical-CVE scan, GHCR push on
push events), **validate-deploy** (helm lint + kubeconform + terraform
validate). To demo the gate catching a regression: edit a `must_cite` in
`eval/golden.jsonl` to a bogus id and push — eval-gate goes red.

Branch protection (Settings → Branches → protect `main`): require the
`lint-test` and `eval-gate` checks before merge.

## 10. Load test + release polish

```powershell
winget install k6
k6 run load/search_test.js
k6 run load/chat_test.js     # keep gpu profile up; watch nvidia-smi + Grafana
```

Record p50/p95 and tokens/s in the README, take Grafana screenshots, then:

```powershell
git tag v1.0
git push --tags
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `--gpus all` → "could not select device driver" | Docker Desktop → Settings → enable GPU / WSL integration; update the NVIDIA **Windows** driver |
| vLLM crashes with `RuntimeError: UVA is not available` | Known issue with vLLM's newest releases under Docker Desktop's WSL2 GPU passthrough (their V2 GPU model runner requires CUDA Unified Virtual Addressing, which WSL2 passthrough doesn't expose). Already fixed here by pinning `vllm/vllm-openai:v0.7.3` in docker-compose.yaml instead of `:latest` — verified working on RTX 3060/WSL2. If you bump the tag, re-verify this still works. |
| vLLM: CUDA out of memory | Lower `--max-model-len` to 2048 or `--gpu-memory-utilization` to 0.7 in docker-compose.yaml; close other GPU apps |
| vLLM: shared-memory RuntimeError | `ipc: host` is already set in compose — if running `docker run` manually, add `--ipc=host` |
| First /chat very slow | First call downloads weights + compiles CUDA graphs; send one warm-up request |
| /health stuck unhealthy on first boot | Embedding models still downloading into the model-cache volume — watch `docker logs -f search-api` |
| Sparse-vector errors on /search | You changed schema without re-ingesting — run `docker compose exec api python -m src.ingest` |
| kind pods `ErrImageNeverPull`/`ImagePullBackOff` | You skipped `kind load docker-image ragship:local --name ragship` |
| Pod can't reach vLLM (`vllm` name fails) | Verify gpu profile is running and port 8001 answers on the host; if `host.docker.internal` doesn't resolve in pods, add a `hostAliases` entry with your host IP to the deployment |
| Eval score is 0 | Corpus not ingested into the Qdrant the eval points at — re-run ingest with the same env |
| Semantic cache never hits | Lower `SEMANTIC_CACHE_THRESHOLD` to 0.95 |
| GHCR push denied in CI | The workflow already sets `packages: write`; also check repo Settings → Actions → Workflow permissions → "Read and write" |
