FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install shared-types package first (path dependency)
COPY ../../packages/shared-types /packages/shared-types
RUN pip install --no-cache-dir /packages/shared-types

# Copy and install project dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# Copy application source
COPY ai_agent_runner/ ./ai_agent_runner/

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
  CMD curl -sf http://localhost:8000/health || exit 1

CMD ["uvicorn", "ai_agent_runner.main:app", "--host", "0.0.0.0", "--port", "8000"]
