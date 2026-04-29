FROM python:3.12-slim

WORKDIR /app

# Install poetry
RUN pip install --no-cache-dir poetry==1.8.3

# Copy dependency files
COPY pyproject.toml poetry.lock* ./
COPY ../../packages/shared-types /packages/shared-types

# Install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root

# Copy source
COPY . .

CMD ["uvicorn", "model_registry_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
