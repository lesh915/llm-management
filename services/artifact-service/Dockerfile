# Build context: project root (.)
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir poetry==1.8.3

# shared-types는 루트 컨텍스트 기준 경로로 복사
COPY packages/shared-types /packages/shared-types

COPY services/artifact-service/pyproject.toml services/artifact-service/poetry.lock* ./

RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root

COPY services/artifact-service/ .

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
  CMD curl -sf http://localhost:8000/health || exit 1

CMD ["uvicorn", "artifact_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
