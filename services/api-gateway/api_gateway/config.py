"""API Gateway 설정."""
from __future__ import annotations

import os

# ── 업스트림 서비스 URL ─────────────────────────────────────────────────────────

ARTIFACT_SERVICE_URL    = os.environ.get("ARTIFACT_SERVICE_URL",    "http://artifact-service:8000")
MODEL_REGISTRY_URL      = os.environ.get("MODEL_REGISTRY_URL",      "http://model-registry-service:8000")
COMPARISON_ENGINE_URL   = os.environ.get("COMPARISON_ENGINE_URL",   "http://comparison-engine:8000")
AIOPS_SERVICE_URL       = os.environ.get("AIOPS_SERVICE_URL",       "http://aiops-service:8000")
AI_AGENT_RUNNER_URL     = os.environ.get("AI_AGENT_RUNNER_URL",     "http://ai-agent-runner:8000")

# ── 인증 설정 ──────────────────────────────────────────────────────────────────

JWT_SECRET  = os.environ.get("JWT_SECRET",  "change-me-in-production")
JWT_ALG     = os.environ.get("JWT_ALG",     "HS256")
JWT_EXPIRE  = int(os.environ.get("JWT_EXPIRE_MINUTES", "60"))

# API Key 인증 (단순 헤더 검사)
GATEWAY_API_KEY = os.environ.get("GATEWAY_API_KEY", "")

# ── 기타 ───────────────────────────────────────────────────────────────────────

PROXY_TIMEOUT = float(os.environ.get("PROXY_TIMEOUT", "30"))
