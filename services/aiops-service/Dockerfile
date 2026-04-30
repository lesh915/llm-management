FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

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

EXPOSE 8000

CMD ["uvicorn", "aiops_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
