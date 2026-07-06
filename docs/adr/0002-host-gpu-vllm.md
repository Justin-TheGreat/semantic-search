# ADR 0002 — vLLM stays on the host GPU; the cluster reaches it via ExternalName

**Status:** accepted

## Context

Phase 7 moves the platform into a local kind (Kubernetes-in-Docker) cluster.
The LLM tier (vLLM + Qwen2.5-0.5B-Instruct) needs the single consumer GPU.
GPU passthrough *into* kind nodes is possible but fragile on Docker
Desktop/WSL2 and adds no portfolio-relevant signal beyond the pain itself.

## Decision

Keep vLLM running on the host (compose `gpu` profile, port 8001) and expose it
to in-cluster pods with a Kubernetes `ExternalName` Service:

```
vllm (ExternalName) -> host.docker.internal -> host port 8001 -> vLLM container
```

The app reads `VLLM_BASE_URL`, so the same image works in compose
(`http://vllm:8000/v1`) and in the cluster (`http://vllm:8001/v1` through the
ExternalName).

## Consequences

- One GPU serves both compose and cluster environments simultaneously.
- The cluster has a hard runtime dependency on a host process — acceptable for
  a local lab, and documented. `/chat` degrades to a 503-style error event
  when the LLM is unreachable while `/search` keeps working.
- The true in-cluster alternative (NVIDIA device plugin, KubeRay RayService)
  is recorded as the stretch path.
