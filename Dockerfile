# ═══ STAGE 1: builder (heavy, has pip + compilers) ═══
FROM python:3.11-slim-bookworm@sha256:6e61454355fe0dbb41d9779857c6507681af1b7b196f7485b44c9d2d272a3df0 AS builder

# Install build tools needed for some packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /install
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ═══ STAGE 2: test (runs pytest, fails build if tests fail) ═══
FROM builder AS test
WORKDIR /app
COPY requirements-dev.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements-dev.txt
COPY src/ ./src/
COPY tests/ ./tests/
ENV PYTHONPATH=/app
RUN PATH=/install/bin:$PATH PYTHONPATH=/install/lib/python3.11/site-packages:/app pytest tests/ -v


# ═══ STAGE 3: runtime (lean, final image) ═══
FROM python:3.11-slim-bookworm@sha256:6e61454355fe0dbb41d9779857c6507681af1b7b196f7485b44c9d2d272a3df0 AS runtime

# Install only runtime deps (curl needed for healthcheck)
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder, leave compilers behind
COPY --from=builder /install /usr/local

WORKDIR /app
COPY src/ ./src/

# Create non-root user for security
RUN useradd --create-home --uid 1001 appuser && \
    mkdir -p /models && \
    chown -R appuser:appuser /app /models
USER appuser

ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]