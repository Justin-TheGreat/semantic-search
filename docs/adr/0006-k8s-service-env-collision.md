# ADR 0006 — Explicitly pin QDRANT_PORT/DB_PORT/REDIS_PORT in the Helm chart

**Status:** accepted

## Context

During the first live `terraform apply` + `kind load docker-image` run
(2026-07-12), the `ragship` pod crash-looped on startup with:

```
pydantic_core._pydantic_core.ValidationError: 2 validation errors for Settings
qdrant_port
  Input should be a valid integer, unable to parse string as an integer
  [type=int_parsing, input_value='tcp://10.96.122.173:6333', ...]
redis_port
  Input should be a valid integer, unable to parse string as an integer
  [type=int_parsing, input_value='tcp://10.96.36.171:6379', ...]
```

Kubernetes automatically injects legacy Docker-links-style environment
variables into every pod for every Service that already exists in the same
namespace — `<SVCNAME>_PORT=tcp://<clusterIP>:<port>` alongside the modern
`<SVCNAME>_SERVICE_HOST`/`_SERVICE_PORT` pair. Because the Qdrant and Redis
Services are named exactly `qdrant` and `redis`, Kubernetes injects
`QDRANT_PORT` and `REDIS_PORT` — which collide with `Settings.qdrant_port` /
`Settings.redis_port` in [src/config.py](../../src/config.py), since
pydantic-settings binds env vars to fields case-insensitively by default. The
Postgres Service is named `postgresql`, not `db`, so `DB_PORT` was not
auto-injected and `db_port` was unaffected — pure naming coincidence, not a
structural difference.

This never surfaced in `docker compose`, which has no such auto-injection
mechanism — only real Kubernetes exposed it.

## Decision

Pin `QDRANT_PORT`, `DB_PORT`, and `REDIS_PORT` explicitly in
[deploy/helm/ragship/templates/deployment.yaml](../../deploy/helm/ragship/templates/deployment.yaml),
alongside the existing `*_HOST` vars. Explicit container-spec `env` entries
take precedence over Kubernetes' auto-injected service-link variables of the
same name, so this reliably wins regardless of Service naming.

## Consequences

- The chart is now immune to this class of collision even if a dependency
  Service is later renamed to something that happens to match a Settings
  field (e.g. `redis` → `cache` would be fine either way now).
- General lesson for this codebase: any `Settings` field whose name matches a
  plausible Kubernetes Service name is a latent collision. New integer/URL
  config fields added to `src/config.py` should get an explicit env pin in
  the Helm chart if there's any chance a Service will share that name.
