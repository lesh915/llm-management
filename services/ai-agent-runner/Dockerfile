# Build context: project root (.)
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# shared-types를 먼저 설치 (file:// 경로 의존성 해결)
COPY packages/shared-types /packages/shared-types
RUN pip install --no-cache-dir /packages/shared-types

# pyproject.toml 복사 후 shared-types 라인 제거(이미 설치됨)하고 나머지 의존성 설치
COPY services/ai-agent-runner/pyproject.toml ./pyproject.toml
RUN sed -i '/shared-types/d' pyproject.toml \
    && pip install --no-cache-dir \
        "fastapi>=0.111.0" \
        "uvicorn[standard]>=0.29.0" \
        "anthropic>=0.28.0" \
        "httpx>=0.27.0" \
        "pydantic>=2.7.0"

# 소스 복사
COPY services/ai-agent-runner/ai_agent_runner/ ./ai_agent_runner/

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
  CMD curl -sf http://localhost:8000/health || exit 1

CMD ["uvicorn", "ai_agent_runner.main:app", "--host", "0.0.0.0", "--port", "8000"]
