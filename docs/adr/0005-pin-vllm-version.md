# ADR 0005 — Pin vLLM to v0.7.3 instead of `:latest`

**Status:** accepted

## Context

During the first live test run of the capstone (2026-07-12), `docker compose
--profile gpu up vllm` using `vllm/vllm-openai:latest` crashed on startup:

```
RuntimeError: UVA is not available
```

`:latest` resolved to vLLM 0.25.0, whose newer V2 GPU model runner allocates a
staged-write buffer that requires CUDA Unified Virtual Addressing. Docker
Desktop's WSL2 GPU passthrough layer does not expose UVA the way a native
Linux + NVIDIA driver stack does, so engine init fails before the server ever
binds a port. This reproduced identically both via `docker compose` and a bare
`docker run`, and was unaffected by `VLLM_USE_V1=0` (not a recognized env var
in this release).

## Decision

Pin the compose `vllm` service to `vllm/vllm-openai:v0.7.3`, the last release
line using the V0 engine (`llm_engine.py` / `worker.py`), which has no UVA
dependency. Verified end-to-end on this machine (RTX 3060 12GB, Docker
Desktop, WSL2 Ubuntu-24.04): model loads, KV cache computes (42862 GPU
blocks at `--gpu-memory-utilization 0.85`, `--max-model-len 4096`), CUDA
graphs capture, and `/v1/chat/completions` returns real generations. The full
`/chat` SSE pipeline and the `--with-llm` eval harness (score 0.900) were
exercised against this exact image.

## Consequences

- Loses whatever throughput/feature improvements landed in vLLM between 0.7.3
  and the current `latest` — acceptable for a 0.5B model on one consumer GPU.
- `:latest` is not safe to use unpinned on this class of environment (WSL2 GPU
  passthrough). Anyone bumping the vLLM version must re-verify a full `/chat`
  round trip before merging, not just that the container starts.
- This is themed the same way as ADR 0004 (Bitnami charts): "latest"/"stable"
  tags on fast-moving ML infra images are a real reliability risk, not a
  hypothetical one — both were caught only by actually running the stack.
