# Build context: project root (.)
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir poetry==1.8.3

COPY packages/shared-types   /packages/shared-types
COPY services/llm-adapter    /services/llm-adapter

COPY services/comparison-engine/pyproject.toml services/comparison-engine/poetry.lock* ./

RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root

COPY services/comparison-engine/ .

EXPOSE 8000

CMD ["uvicorn", "comparison_engine.main:app", "--host", "0.0.0.0", "--port", "8000"]
