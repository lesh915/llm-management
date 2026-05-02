# Build context: project root (.)
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir poetry==1.8.3

COPY packages/shared-types /packages/shared-types
COPY services/llm-adapter /services/llm-adapter

COPY services/model-registry-service/pyproject.toml services/model-registry-service/poetry.lock* ./

RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root

COPY services/model-registry-service/ .

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
  CMD curl -sf http://localhost:8000/health || exit 1

CMD ["uvicorn", "model_registry_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
