FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir poetry==1.8.3

COPY pyproject.toml poetry.lock* ./
COPY ../../packages/shared-types /packages/shared-types
COPY ../../services/llm-adapter   /services/llm-adapter

RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root

COPY . .

CMD ["uvicorn", "comparison_engine.main:app", "--host", "0.0.0.0", "--port", "8000"]
