# LLM Management System — 개발 가이드

**버전**: 1.1.0  
**기준 문서**: LLM-PRD.md v1.0.0  
**작성일**: 2026-04-26  
**변경 이력**: v1.1.0 — 로컬 LLM(Ollama, vLLM 등) 비교 지원 추가

---

## 목차

1. [프로젝트 구조](#1-프로젝트-구조)
2. [기술 스택](#2-기술-스택)
3. [환경 설정](#3-환경-설정)
4. [서비스별 구현 가이드](#4-서비스별-구현-가이드)
5. [데이터 모델 구현](#5-데이터-모델-구현)
6. [API 설계 규칙](#6-api-설계-규칙)
7. [LLM 어댑터 레이어](#7-llm-어댑터-레이어)
8. [로컬 LLM 연동 가이드](#8-로컬-llm-연동-가이드)
9. [테스트 전략](#9-테스트-전략)
10. [Phase별 개발 체크리스트](#10-phase별-개발-체크리스트)
11. [운영 가이드](#11-운영-가이드)

---

## 1. 프로젝트 구조

```
llm-management/
├── services/
│   ├── artifact-service/        # 모듈 A: 에이전트 아티팩트 관리
│   ├── model-registry-service/  # 모듈 B: LLM 모델 레지스트리
│   ├── comparison-engine/       # 모듈 C: 다모델 비교 분석
│   ├── aiops-service/           # 모듈 D: AIOps 모니터링
│   ├── ai-agent-runner/         # 모듈 D: AI 에이전트 실행 환경
│   ├── llm-adapter/             # 공통: LLM 공급자 추상화
│   └── api-gateway/             # 공통: API 게이트웨이
├── packages/
│   ├── sdk-python/              # Python SDK
│   ├── sdk-typescript/          # TypeScript SDK
│   └── shared-types/            # 공유 타입 정의
├── infra/
│   ├── docker/
│   ├── k8s/
│   └── migrations/
└── web/                         # Web UI
```

### 서비스 간 의존성

```
api-gateway
    ├── artifact-service      → PostgreSQL, S3
    ├── model-registry-service → PostgreSQL
    ├── comparison-engine     → model-registry-service, llm-adapter, S3
    ├── aiops-service         → TimeSeries DB, ai-agent-runner
    └── ai-agent-runner       → llm-adapter, artifact-service
```

---

## 2. 기술 스택

| 계층 | 기술 | 선택 이유 |
|------|------|-----------|
| **백엔드 런타임** | Python 3.12+ (FastAPI) | Anthropic SDK 지원, 비동기 처리 |
| **메타데이터 DB** | PostgreSQL 16 | 관계형 데이터, JSONB 지원 |
| **아티팩트 스토리지** | S3 / MinIO (self-hosted) | 대용량 아티팩트 저장 |
| **시계열 DB** | TimescaleDB (PostgreSQL 확장) | 운영 지표 저장, SQL 호환 |
| **메시지 브로커** | Redis Streams | 비교 태스크 큐, 실시간 이벤트 |
| **캐시** | Redis | API 응답 캐시, 세션 |
| **Web UI** | Next.js 15 + React | SSR, App Router |
| **API 문서** | OpenAPI 3.1 (자동 생성) | FastAPI 내장 |
| **컨테이너** | Docker + Kubernetes | 서비스 격리, 확장성 |
| **로컬 LLM** | Ollama / vLLM | OpenAI-compatible API, 로컬 실행 |

### Python 의존성 (핵심)

```toml
# pyproject.toml
[tool.poetry.dependencies]
python = "^3.12"
fastapi = "^0.115"
sqlalchemy = {extras = ["asyncio"], version = "^2.0"}
alembic = "^1.13"
pydantic = "^2.0"
anthropic = "^0.50"          # Anthropic SDK (prompt caching 포함)
openai = "^1.50"
redis = {extras = ["hiredis"], version = "^5.0"}
boto3 = "^1.35"              # S3
httpx = "^0.27"
celery = "^5.4"              # 비교 태스크 비동기 실행
```

---

## 3. 환경 설정

### 3.1 로컬 개발 환경

```bash
# 필수 서비스 실행
docker compose up -d postgres redis minio

# 환경 변수
cp .env.example .env
```

```dotenv
# .env
DATABASE_URL=postgresql+asyncpg://llm_mgmt:password@localhost:5432/llm_mgmt
REDIS_URL=redis://localhost:6379/0
S3_ENDPOINT=http://localhost:9000
S3_BUCKET=llm-management

# LLM API Keys (필요한 공급자만)
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=...

# 로컬 LLM (Ollama / vLLM)
OLLAMA_BASE_URL=http://localhost:11434    # Ollama 기본값
VLLM_BASE_URL=http://localhost:8000      # vLLM 기본값

# 암호화 (API 키 저장용)
ENCRYPTION_KEY=...  # Fernet 32-byte base64 key
```

### 3.2 서비스 시작

```bash
# 마이그레이션
alembic upgrade head

# 서비스 실행 (개발)
uvicorn artifact_service.main:app --reload --port 8001
uvicorn model_registry_service.main:app --reload --port 8002
uvicorn comparison_engine.main:app --reload --port 8003
uvicorn aiops_service.main:app --reload --port 8004

# Celery worker (비교 태스크 처리)
celery -A comparison_engine.worker worker --loglevel=info
```

---

## 4. 서비스별 구현 가이드

### 4.1 artifact-service (모듈 A)

**책임**: 에이전트 아티팩트 CRUD, 버전 관리, 의존성 분석

#### 핵심 엔드포인트

```
POST   /agents                          # 에이전트 등록
GET    /agents/{agent_id}
POST   /agents/{agent_id}/artifacts     # 아티팩트 등록 (FR-A1)
GET    /agents/{agent_id}/artifacts
POST   /artifacts/{artifact_id}/analyze # 의존성 분석 실행 (FR-A2)
GET    /artifacts/{artifact_id}/impact  # 영향 분석 (FR-A3)
  ?source_model_id=...
  &target_model_id=...
POST   /artifacts/{artifact_id}/variants # 모델 변형 등록 (FR-A4)
```

#### 의존성 분석기 구현 (FR-A2)

아티팩트 등록 시 자동으로 모델 특화 기능 의존성을 감지한다.

```python
# artifact_service/analyzers/dependency_analyzer.py

from enum import Enum
from dataclasses import dataclass

class CompatibilityLevel(str, Enum):
    COMPATIBLE = "compatible"
    PARTIAL = "partial"
    INCOMPATIBLE = "incompatible"

@dataclass
class ModelDependency:
    feature: str           # e.g., "tool_choice_required", "vision", "json_mode"
    required: bool
    description: str

class ArtifactDependencyAnalyzer:
    """아티팩트에서 모델 특화 기능 의존성을 자동 감지"""

    def analyze(self, artifact_type: str, content: dict) -> list[ModelDependency]:
        deps = []
        if artifact_type == "mcp":
            deps.extend(self._analyze_mcp(content))
        elif artifact_type == "prompt":
            deps.extend(self._analyze_prompt(content))
        elif artifact_type == "tool_schema":
            deps.extend(self._analyze_tool_schema(content))
        return deps

    def _analyze_mcp(self, content: dict) -> list[ModelDependency]:
        deps = []
        # tool_choice: "required" 감지
        if content.get("tool_choice") == "required":
            deps.append(ModelDependency(
                feature="tool_choice_required",
                required=True,
                description="도구 호출이 필수로 강제됨"
            ))
        # parallel tool calls 감지
        if content.get("parallel_tool_calls"):
            deps.append(ModelDependency(
                feature="parallel_tool_calls",
                required=False,
                description="병렬 도구 호출 사용"
            ))
        return deps

    def check_compatibility(
        self,
        dependencies: list[ModelDependency],
        model_capabilities: dict
    ) -> CompatibilityLevel:
        incompatible = [
            d for d in dependencies
            if d.required and not model_capabilities.get(d.feature, False)
        ]
        partial = [
            d for d in dependencies
            if not d.required and not model_capabilities.get(d.feature, False)
        ]
        if incompatible:
            return CompatibilityLevel.INCOMPATIBLE
        if partial:
            return CompatibilityLevel.PARTIAL
        return CompatibilityLevel.COMPATIBLE
```

#### 버전 관리

아티팩트 업데이트 시 기존 버전을 보존하고 새 버전을 생성한다.

```python
async def update_artifact(artifact_id: str, content: dict, db: AsyncSession):
    artifact = await db.get(AgentArtifact, artifact_id)
    # 이전 버전 스냅샷을 S3에 저장
    await s3_client.put_object(
        key=f"artifacts/{artifact_id}/v{artifact.version}.json",
        body=artifact.content
    )
    artifact.version += 1
    artifact.content = content
    artifact.updated_at = datetime.utcnow()
    await db.commit()
```

---

### 4.2 model-registry-service (모듈 B)

**책임**: LLM 모델 메타데이터 관리, 호환성 매핑, 생명주기 관리

#### 핵심 엔드포인트

```
POST   /models                          # 모델 등록 (FR-B1)
GET    /models
GET    /models/{model_id}
PATCH  /models/{model_id}/status        # 상태 변경 (FR-B3)
GET    /models/compare                  # 비교 매트릭스 (FR-B2)
  ?model_ids=id1,id2,id3
  &filter_vision=true
  &filter_tool_use=true
POST   /models/{model_id}/compatibility # 아티팩트 호환성 체크
```

#### 모델 등록 스키마

```python
# model_registry_service/schemas.py

from pydantic import BaseModel, Field
from typing import Literal

class ModelCapabilities(BaseModel):
    context_window: int
    max_output_tokens: int
    vision: bool = False
    tool_use: bool = False
    structured_output: bool = False
    streaming: bool = True
    parallel_tool_calls: bool = False
    extended_thinking: bool = False

class ModelCharacteristics(BaseModel):
    reasoning_depth: Literal["low", "medium", "high"]
    instruction_following: Literal["low", "medium", "high"]
    code_generation: Literal["low", "medium", "high"]
    latency_tier: Literal["low", "medium", "high"]

class ModelPricing(BaseModel):
    input_per_1m_tokens: float   # USD
    output_per_1m_tokens: float  # USD

class ModelApiConfig(BaseModel):
    endpoint: str
    auth_type: Literal["api_key", "oauth", "custom"]
    sdk: list[str] = []

class ModelCreate(BaseModel):
    id: str = Field(..., example="claude-sonnet-4-6")
    provider: str
    family: str
    version: str
    capabilities: ModelCapabilities
    characteristics: ModelCharacteristics
    pricing: ModelPricing
    api: ModelApiConfig
    is_custom: bool = False      # 커스텀/자체호스팅 모델 (FR-B4)
    custom_adapter: str | None = None
```

#### API 키 암호화 저장

```python
# model_registry_service/security.py
from cryptography.fernet import Fernet
import os

_fernet = Fernet(os.environ["ENCRYPTION_KEY"].encode())

def encrypt_api_key(key: str) -> str:
    return _fernet.encrypt(key.encode()).decode()

def decrypt_api_key(encrypted: str) -> str:
    return _fernet.decrypt(encrypted.encode()).decode()
```

#### deprecated 알림 (FR-B3)

```python
async def deprecate_model(model_id: str, db: AsyncSession):
    model = await db.get(ModelRegistry, model_id)
    model.status = "deprecated"
    model.deprecated_at = datetime.utcnow()

    # 해당 모델을 사용 중인 아티팩트 소유자 조회
    affected = await db.execute(
        select(AgentArtifact).where(
            AgentArtifact.model_requirements.contains([model_id])
        )
    )
    # 알림 발송 (이메일 / 웹훅)
    for artifact in affected.scalars():
        await notification_service.send(
            owner=artifact.owner,
            message=f"모델 {model_id}가 deprecated 예정입니다. "
                    f"영향받는 아티팩트: {artifact.id}"
        )
    await db.commit()
```

---

### 4.3 comparison-engine (모듈 C)

**책임**: 비교 태스크 스케줄링, 병렬 실행, 결과 집계 및 리포트 생성

#### 핵심 엔드포인트

```
POST   /tasks                           # 비교 태스크 생성 (FR-C1)
POST   /tasks/{task_id}/run             # 태스크 실행 (FR-C2)
GET    /tasks/{task_id}/status          # 실행 상태 조회
GET    /tasks/{task_id}/report          # 결과 리포트 (FR-C3)
GET    /tasks/{task_id}/recommendation  # 권장 모델 (FR-C4)
POST   /tasks/ab-compare               # A/B 비교 (FR-C5)
```

#### 병렬 실행 구현 (FR-C2)

```python
# comparison_engine/runner.py
import asyncio
from anthropic import AsyncAnthropic

async def run_comparison_task(task: ComparisonTask) -> list[ComparisonResult]:
    """모든 대상 모델에 대해 동시 평가 실행"""
    dataset = await load_dataset(task.dataset_id)

    # 모델별 평가를 병렬로 실행
    results = await asyncio.gather(*[
        evaluate_model(model_id, task, dataset)
        for model_id in task.model_ids
    ], return_exceptions=True)

    return [r for r in results if not isinstance(r, Exception)]

async def evaluate_model(
    model_id: str,
    task: ComparisonTask,
    dataset: list[EvalCase]
) -> ComparisonResult:
    adapter = get_adapter(model_id)
    outputs = []
    total_cost = 0.0

    for case in dataset:
        response = await adapter.complete(
            messages=case.input_messages,
            tools=case.tools,
        )
        outputs.append({
            "case_id": case.id,
            "output": response.content,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "latency_ms": response.latency_ms,
        })
        total_cost += calculate_cost(model_id, response.usage)

        # 진행 상태 업데이트 (Redis pub/sub)
        await progress_publisher.publish(task.id, model_id, len(outputs), len(dataset))

    metrics = calculate_metrics(outputs, dataset, task.metrics)
    return ComparisonResult(task_id=task.id, model_id=model_id, metrics=metrics,
                            raw_outputs=outputs, cost_usd=total_cost)
```

#### 지표 계산

```python
# comparison_engine/metrics.py

def calculate_metrics(
    outputs: list[dict],
    dataset: list[EvalCase],
    requested_metrics: list[str]
) -> dict:
    metrics = {}

    if "correctness" in requested_metrics:
        correct = sum(
            1 for o, c in zip(outputs, dataset)
            if normalize(o["output"]) == normalize(c.expected_output)
        )
        metrics["correctness"] = correct / len(dataset)

    if "tool_call_accuracy" in requested_metrics:
        metrics["tool_call_accuracy"] = _tool_call_accuracy(outputs, dataset)

    if "latency_p95" in requested_metrics:
        latencies = sorted(o["latency_ms"] for o in outputs)
        p95_idx = int(len(latencies) * 0.95)
        metrics["latency_p95"] = latencies[p95_idx]

    if "cost_per_query" in requested_metrics:
        total_cost = sum(
            o["input_tokens"] * pricing.input + o["output_tokens"] * pricing.output
            for o in outputs
        )
        metrics["cost_per_query"] = total_cost / len(outputs)

    return metrics
```

#### 권장 모델 제안 (FR-C4)

```python
# comparison_engine/recommender.py

PRIORITY_WEIGHTS = {
    "cost":        {"cost_per_query": 0.6, "correctness": 0.3, "latency_p95": 0.1},
    "performance": {"correctness": 0.5, "tool_call_accuracy": 0.3, "latency_p95": 0.2},
    "balanced":    {"correctness": 0.35, "cost_per_query": 0.35, "latency_p95": 0.3},
}

def recommend_model(
    results: list[ComparisonResult],
    priority: str = "balanced"
) -> dict:
    weights = PRIORITY_WEIGHTS[priority]
    scores = {}

    for result in results:
        score = 0.0
        for metric, weight in weights.items():
            normalized = normalize_metric(metric, result.metrics.get(metric, 0))
            # cost는 낮을수록 좋으므로 역수 처리
            if metric in ("cost_per_query", "latency_p95"):
                normalized = 1 - normalized
            score += normalized * weight
        scores[result.model_id] = score

    best_model_id = max(scores, key=scores.get)
    return {
        "recommended_model": best_model_id,
        "scores": scores,
        "rationale": generate_rationale(results, best_model_id, priority),
    }
```

---

### 4.4 aiops-service (모듈 D)

**책임**: 운영 지표 수집, 이상 탐지, 알림 트리거

#### 핵심 엔드포인트

```
POST   /metrics                         # 지표 수집 (FR-D1)
GET    /metrics/{agent_id}
  ?from=...&to=...&metric=latency
GET    /events                          # AIOps 이벤트 목록 (FR-D2)
GET    /events/{event_id}
PATCH  /events/{event_id}/approve       # 조치 승인 (FR-D3)
POST   /rules                           # 자동화 규칙 등록 (FR-D4)
GET    /reports/daily                   # 운영 리포트 (FR-D5)
```

#### 이상 탐지 구현 (FR-D2)

```python
# aiops_service/detectors/anomaly_detector.py

class AnomalyDetector:
    THRESHOLDS = {
        "error_rate_spike":    {"delta_pct": 5.0,   "window_min": 5},
        "latency_p95_breach":  {"absolute": None,   "window_min": 5},   # 모델별 설정
        "cost_budget_breach":  {"budget_usd": None, "window_min": 60},
        "tool_call_failure":   {"delta_pct": 3.0,   "window_min": 5},
    }

    async def check(self, agent_id: str, model_id: str, tsdb: TimescaleDB):
        events = []

        # 오류율 급증 감지
        current_error_rate = await tsdb.query_avg(
            "error_rate", agent_id, model_id, minutes=5
        )
        baseline_error_rate = await tsdb.query_avg(
            "error_rate", agent_id, model_id, minutes=60
        )
        delta = current_error_rate - baseline_error_rate
        if delta > self.THRESHOLDS["error_rate_spike"]["delta_pct"]:
            events.append(AIOpsEvent(
                agent_id=agent_id,
                model_id=model_id,
                event_type="error_rate_spike",
                severity="high",
                description=f"오류율 {delta:.1f}%p 급증 (현재: {current_error_rate:.1f}%)"
            ))

        return events
```

---

### 4.5 ai-agent-runner (모듈 D)

**책임**: AIOps 이벤트 처리 AI 에이전트 실행 (진단 → 조치 제안 → 실행)

#### Claude SDK를 활용한 진단 에이전트 (FR-D3)

```python
# ai_agent_runner/diagnosis_agent.py
import anthropic

client = anthropic.AsyncAnthropic()

DIAGNOSIS_TOOLS = [
    {
        "name": "query_metrics",
        "description": "특정 에이전트의 운영 지표를 조회합니다",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string"},
                "metric": {"type": "string",
                           "enum": ["error_rate", "latency_p95", "tool_call_failure_rate"]},
                "window_minutes": {"type": "integer"},
            },
            "required": ["agent_id", "metric"],
        },
    },
    {
        "name": "get_recent_logs",
        "description": "에이전트의 최근 오류 로그를 조회합니다",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
                "level": {"type": "string", "enum": ["error", "warn"]},
            },
            "required": ["agent_id"],
        },
    },
    {
        "name": "propose_action",
        "description": "진단 결과를 바탕으로 조치 방안을 제안합니다",
        "input_schema": {
            "type": "object",
            "properties": {
                "root_cause": {"type": "string"},
                "actions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string",
                                     "enum": ["rollback", "switch_model", "fix_schema", "adjust_params"]},
                            "description": {"type": "string"},
                            "risk_level": {"type": "string", "enum": ["low", "medium", "high"]},
                        },
                    },
                },
            },
            "required": ["root_cause", "actions"],
        },
    },
]

async def run_diagnosis_agent(event: AIOpsEvent) -> DiagnosisResult:
    """AIOps 이벤트에 대한 AI 진단 에이전트 실행"""
    messages = [{
        "role": "user",
        "content": f"""AIOps 이벤트가 발생했습니다. 진단해 주세요.

이벤트 유형: {event.event_type}
에이전트 ID: {event.agent_id}
모델: {event.model_id}
설명: {event.description}

도구를 사용하여 지표와 로그를 분석하고, 근본 원인을 파악한 후 조치 방안을 제안하세요."""
    }]

    # 프롬프트 캐싱 적용 (시스템 프롬프트 재사용 최적화)
    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=[{
            "type": "text",
            "text": "당신은 AI 운영 전문가입니다. 에이전트 운영 이슈를 진단하고 실행 가능한 조치를 제안합니다.",
            "cache_control": {"type": "ephemeral"},
        }],
        tools=DIAGNOSIS_TOOLS,
        messages=messages,
    )

    return await process_agent_response(response, event, messages)
```

---

## 5. 데이터 모델 구현

### 5.1 PostgreSQL 스키마

```sql
-- migrations/001_initial_schema.sql

CREATE TABLE agents (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(255) NOT NULL,
    description TEXT,
    owner       VARCHAR(255) NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE agent_artifacts (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id           UUID REFERENCES agents(id) ON DELETE CASCADE,
    type               VARCHAR(50) NOT NULL CHECK (type IN ('prompt', 'mcp', 'skill', 'tool_schema')),
    content            JSONB NOT NULL,
    version            INTEGER NOT NULL DEFAULT 1,
    model_requirements JSONB DEFAULT '[]',   -- 감지된 모델 기능 의존성
    created_at         TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE model_registry (
    id              VARCHAR(100) PRIMARY KEY,   -- e.g., "claude-sonnet-4-6"
    provider        VARCHAR(100) NOT NULL,
    family          VARCHAR(100),
    version         VARCHAR(50),
    capabilities    JSONB NOT NULL,
    characteristics JSONB NOT NULL,
    pricing         JSONB NOT NULL,
    api_config      JSONB NOT NULL,
    status          VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'deprecated', 'retired')),
    is_custom       BOOLEAN DEFAULT FALSE,
    deprecated_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE model_variants (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_id UUID REFERENCES agent_artifacts(id) ON DELETE CASCADE,
    model_id    VARCHAR(100) REFERENCES model_registry(id) ON DELETE CASCADE,
    content     JSONB NOT NULL,
    notes       TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(artifact_id, model_id)
);

CREATE TABLE comparison_tasks (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name         VARCHAR(255) NOT NULL,
    artifact_id  UUID REFERENCES agent_artifacts(id),
    model_ids    TEXT[] NOT NULL,
    dataset_id   VARCHAR(255) NOT NULL,
    metrics      TEXT[] NOT NULL,
    status       VARCHAR(20) DEFAULT 'pending'
                     CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE comparison_results (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id     UUID REFERENCES comparison_tasks(id) ON DELETE CASCADE,
    model_id    VARCHAR(100) REFERENCES model_registry(id) ON DELETE CASCADE,
    metrics     JSONB NOT NULL,
    raw_outputs JSONB,
    cost_usd    DECIMAL(10, 6),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE aiops_events (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id    UUID REFERENCES agents(id),
    model_id    VARCHAR(100) REFERENCES model_registry(id) ON DELETE SET NULL,
    event_type  VARCHAR(100) NOT NULL,
    severity    VARCHAR(20) CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    description TEXT,
    status      VARCHAR(20) DEFAULT 'open'
                    CHECK (status IN ('open', 'diagnosing', 'pending_approval', 'executing', 'resolved')),
    actions     JSONB DEFAULT '[]',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- TimescaleDB 하이퍼테이블 (운영 지표)
CREATE TABLE ops_metrics (
    time        TIMESTAMPTZ NOT NULL,
    agent_id    UUID NOT NULL,
    model_id    VARCHAR(100) NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    value       DOUBLE PRECISION NOT NULL
);
SELECT create_hypertable('ops_metrics', 'time');
CREATE INDEX ON ops_metrics (agent_id, metric_name, time DESC);
```

### 5.2 SQLAlchemy ORM 모델

```python
# shared/models.py
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, JSON, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID, ARRAY
import uuid

class Base(DeclarativeBase):
    pass

class ModelRegistry(Base):
    __tablename__ = "model_registry"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    provider: Mapped[str] = mapped_column(String(100))
    capabilities: Mapped[dict] = mapped_column(JSON)
    characteristics: Mapped[dict] = mapped_column(JSON)
    pricing: Mapped[dict] = mapped_column(JSON)
    api_config: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="active")
    is_custom: Mapped[bool] = mapped_column(Boolean, default=False)
```

---

## 6. API 설계 규칙

### 6.1 응답 형식

모든 API는 다음 형식을 따른다.

```json
// 성공
{
  "data": { ... },
  "meta": { "total": 100, "page": 1, "limit": 20 }
}

// 실패
{
  "error": {
    "code": "MODEL_NOT_FOUND",
    "message": "모델을 찾을 수 없습니다.",
    "details": { "model_id": "gpt-5" }
  }
}
```

### 6.2 에러 코드 정의

| 코드 | HTTP | 설명 |
|------|------|------|
| `ARTIFACT_NOT_FOUND` | 404 | 아티팩트 없음 |
| `MODEL_NOT_FOUND` | 404 | 모델 없음 |
| `MODEL_INCOMPATIBLE` | 422 | 모델 호환 불가 |
| `TASK_ALREADY_RUNNING` | 409 | 태스크 중복 실행 |
| `APPROVAL_REQUIRED` | 403 | 고위험 조치 승인 필요 |
| `LLM_API_ERROR` | 502 | LLM API 오류 |

### 6.3 WebSocket (실시간 상태)

비교 태스크 진행 상태와 AIOps 이벤트는 WebSocket으로 실시간 전달한다.

```
WS /ws/tasks/{task_id}/progress
WS /ws/events/stream?agent_id={agent_id}
```

---

## 7. LLM 어댑터 레이어

각 LLM 공급자(클라우드 + 로컬)를 동일한 인터페이스로 추상화한다.

### 7.1 공통 인터페이스

```python
# llm_adapter/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

@dataclass
class LLMResponse:
    content: str | list
    usage: dict          # input_tokens, output_tokens
    latency_ms: float
    raw: dict            # 공급자별 원본 응답
    is_local: bool = False   # 로컬 실행 여부 (비용 계산 분기용)

@dataclass
class AdapterCapabilities:
    """어댑터가 실제로 지원하는 기능 (런타임 검증용)"""
    tool_use: bool = False
    streaming: bool = True
    parallel_tool_calls: bool = False
    vision: bool = False
    json_mode: bool = False

class BaseLLMAdapter(ABC):
    @abstractmethod
    async def complete(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 4096,
        **kwargs,
    ) -> LLMResponse:
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """어댑터 연결 상태 확인 — 로컬 모델 가용성 체크에 사용"""
        pass

    def get_capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities()
```

### 7.2 클라우드 어댑터

```python
# llm_adapter/anthropic_adapter.py
class AnthropicAdapter(BaseLLMAdapter):
    def __init__(self, model_id: str, api_key: str):
        self.client = AsyncAnthropic(api_key=api_key)
        self.model_id = model_id

    async def complete(self, messages, tools=None, max_tokens=4096, **kwargs):
        start = time.monotonic()
        params = dict(model=self.model_id, max_tokens=max_tokens, messages=messages)
        if tools:
            params["tools"] = tools
        response = await self.client.messages.create(**params)
        return LLMResponse(
            content=response.content,
            usage={"input_tokens": response.usage.input_tokens,
                   "output_tokens": response.usage.output_tokens},
            latency_ms=(time.monotonic() - start) * 1000,
            raw=response.model_dump(),
            is_local=False,
        )

    async def health_check(self) -> bool:
        try:
            await self.client.models.list()
            return True
        except Exception:
            return False

    def get_capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(tool_use=True, streaming=True,
                                   parallel_tool_calls=True, vision=True, json_mode=True)
```

### 7.3 어댑터 팩토리

```python
# llm_adapter/factory.py

def get_adapter(model_id: str) -> BaseLLMAdapter:
    model = model_registry.get(model_id)

    match model.provider:
        case "Anthropic":
            return AnthropicAdapter(model_id, decrypt_api_key(model.api_config["api_key"]))
        case "OpenAI":
            return OpenAICompatAdapter(
                model_id=model_id,
                base_url="https://api.openai.com/v1",
                api_key=decrypt_api_key(model.api_config["api_key"]),
            )
        case "Google":
            return GoogleAdapter(model_id, decrypt_api_key(model.api_config["api_key"]))
        case "Ollama":
            return OllamaAdapter(
                model_name=model.api_config["model_name"],
                base_url=model.api_config.get("endpoint", "http://localhost:11434"),
            )
        case "vLLM" | "LMStudio" | "LocalAI":
            # OpenAI-compatible 로컬 서버 공통 처리
            return OpenAICompatAdapter(
                model_id=model.api_config["model_name"],
                base_url=model.api_config["endpoint"],
                api_key=model.api_config.get("api_key", "local"),  # 로컬은 키 불필요
                is_local=True,
            )
        case _:
            if model.is_custom and model.api_config.get("openai_compat"):
                return OpenAICompatAdapter(
                    model_id=model.api_config["model_name"],
                    base_url=model.api_config["endpoint"],
                    api_key=model.api_config.get("api_key", "local"),
                    is_local=True,
                )
            raise ValueError(f"지원하지 않는 공급자: {model.provider}")
```

---

## 8. 로컬 LLM 연동 가이드

클라우드 API 없이 로컬 머신에서 실행 중인 LLM(Ollama, vLLM, LM Studio, LocalAI 등)을 비교 대상에 포함시킨다. 이 섹션은 등록부터 비교 실행까지 전 과정을 다룬다.

---

### 8.1 지원 로컬 런타임 요약

| 런타임 | API 규격 | 도구 호출 | 추천 용도 |
|--------|----------|-----------|-----------|
| **Ollama** | Ollama 네이티브 + OpenAI-compat | 모델 따라 다름 | 개발·테스트, 다양한 모델 빠른 전환 |
| **vLLM** | OpenAI-compatible | 모델 따라 다름 | GPU 서버 운영, 고처리량 |
| **LM Studio** | OpenAI-compatible | 미지원 (대부분) | 로컬 데스크탑 실험 |
| **LocalAI** | OpenAI-compatible | 일부 지원 | 경량 자체 호스팅 |

> 모든 로컬 런타임은 **OpenAI-compatible 어댑터(`OpenAICompatAdapter`)** 하나로 처리한다.  
> Ollama만 네이티브 어댑터(`OllamaAdapter`)를 추가로 제공하여 Ollama 고유 API(모델 목록 조회, 자동 pull 등)를 활용한다.

---

### 8.2 어댑터 구현

#### OpenAI-Compatible 어댑터 (vLLM / LM Studio / LocalAI 공통)

```python
# llm_adapter/openai_compat_adapter.py
import time
import httpx
from openai import AsyncOpenAI
from .base import BaseLLMAdapter, LLMResponse, AdapterCapabilities

class OpenAICompatAdapter(BaseLLMAdapter):
    """
    OpenAI-compatible REST API를 노출하는 모든 로컬·클라우드 서버에 사용.
    vLLM, LM Studio, LocalAI, 또는 OpenAI 본체.
    """

    def __init__(
        self,
        model_id: str,
        base_url: str,
        api_key: str = "local",
        is_local: bool = False,
        timeout: float = 120.0,   # 로컬 모델은 응답이 느릴 수 있으므로 넉넉히
    ):
        self.model_id = model_id
        self.is_local = is_local
        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=httpx.Timeout(timeout),
        )

    async def complete(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 4096,
        **kwargs,
    ) -> LLMResponse:
        start = time.monotonic()
        params = dict(model=self.model_id, messages=messages, max_tokens=max_tokens)

        if tools:
            # OpenAI 도구 형식으로 변환 (Anthropic 형식으로 등록된 경우 변환 필요)
            params["tools"] = [_to_openai_tool(t) for t in tools]

        response = await self.client.chat.completions.create(**params)
        choice = response.choices[0]

        return LLMResponse(
            content=_extract_content(choice),
            usage={
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
            },
            latency_ms=(time.monotonic() - start) * 1000,
            raw=response.model_dump(),
            is_local=self.is_local,
        )

    async def health_check(self) -> bool:
        try:
            await self.client.models.list()
            return True
        except Exception:
            return False

    def get_capabilities(self) -> AdapterCapabilities:
        # 로컬 서버는 도구 호출 지원 여부가 모델마다 다르므로
        # 모델 레지스트리의 capabilities 값을 신뢰한다.
        return AdapterCapabilities(streaming=True)


def _to_openai_tool(tool: dict) -> dict:
    """Anthropic 도구 스키마 → OpenAI 형식 변환"""
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": tool.get("input_schema", tool.get("parameters", {})),
        },
    }

def _extract_content(choice) -> str | list:
    msg = choice.message
    if msg.tool_calls:
        return [
            {"type": "tool_use", "name": tc.function.name,
             "input": tc.function.arguments}
            for tc in msg.tool_calls
        ]
    return msg.content or ""
```

#### Ollama 네이티브 어댑터

```python
# llm_adapter/ollama_adapter.py
import httpx
import time
from .base import BaseLLMAdapter, LLMResponse, AdapterCapabilities

class OllamaAdapter(BaseLLMAdapter):
    """
    Ollama 네이티브 API 어댑터.
    - /api/chat  : 채팅 완성
    - /api/tags  : 로컬에 설치된 모델 목록
    - /api/pull  : 모델 자동 다운로드 (선택)
    도구 호출이 필요한 경우 Ollama의 OpenAI-compat 엔드포인트(/v1/chat/completions)를
    사용하는 OpenAICompatAdapter로 자동 위임한다.
    """

    def __init__(
        self,
        model_name: str,
        base_url: str = "http://localhost:11434",
        auto_pull: bool = False,   # True면 모델 없을 때 자동 pull
        timeout: float = 120.0,
    ):
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.auto_pull = auto_pull
        self._http = httpx.AsyncClient(timeout=timeout)
        # 도구 호출 시 OpenAI-compat 엔드포인트로 위임
        self._compat = OpenAICompatAdapter(
            model_id=model_name,
            base_url=f"{self.base_url}/v1",
            api_key="ollama",
            is_local=True,
            timeout=timeout,
        )

    async def complete(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 4096,
        **kwargs,
    ) -> LLMResponse:
        # 도구 호출이 필요하면 OpenAI-compat 경로 사용
        if tools:
            return await self._compat.complete(messages, tools, max_tokens, **kwargs)

        if self.auto_pull:
            await self._ensure_model_exists()

        start = time.monotonic()
        resp = await self._http.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model_name,
                "messages": messages,
                "stream": False,
                "options": {"num_predict": max_tokens},
            },
        )
        resp.raise_for_status()
        data = resp.json()

        return LLMResponse(
            content=data["message"]["content"],
            usage={
                # Ollama는 prompt_eval_count / eval_count 필드 사용
                "input_tokens": data.get("prompt_eval_count", 0),
                "output_tokens": data.get("eval_count", 0),
            },
            latency_ms=(time.monotonic() - start) * 1000,
            raw=data,
            is_local=True,
        )

    async def health_check(self) -> bool:
        try:
            resp = await self._http.get(f"{self.base_url}/api/tags", timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False

    async def list_local_models(self) -> list[str]:
        """Ollama에 설치된 모델 이름 목록 반환"""
        resp = await self._http.get(f"{self.base_url}/api/tags")
        resp.raise_for_status()
        return [m["name"] for m in resp.json().get("models", [])]

    async def _ensure_model_exists(self):
        installed = await self.list_local_models()
        if self.model_name not in installed:
            await self._http.post(
                f"{self.base_url}/api/pull",
                json={"name": self.model_name},
                timeout=600.0,  # 대용량 모델 다운로드 대기
            )

    def get_capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(streaming=True, tool_use=True)
```

---

### 8.3 모델 레지스트리에 로컬 모델 등록

#### Ollama 등록 예시 (REST API)

```bash
curl -X POST http://localhost:8002/models \
  -H "Content-Type: application/json" \
  -d '{
    "id": "ollama/llama3.2:3b",
    "provider": "Ollama",
    "family": "Llama 3.2",
    "version": "3b",
    "is_custom": true,
    "capabilities": {
      "context_window": 131072,
      "max_output_tokens": 8192,
      "vision": false,
      "tool_use": true,
      "structured_output": true,
      "streaming": true,
      "parallel_tool_calls": false,
      "extended_thinking": false
    },
    "characteristics": {
      "reasoning_depth": "low",
      "instruction_following": "medium",
      "code_generation": "medium",
      "latency_tier": "low"
    },
    "pricing": {
      "input_per_1m_tokens": 0.0,
      "output_per_1m_tokens": 0.0
    },
    "api": {
      "endpoint": "http://localhost:11434",
      "auth_type": "none",
      "sdk": ["ollama-python"]
    }
  }'
```

#### vLLM 등록 예시

```bash
curl -X POST http://localhost:8002/models \
  -H "Content-Type: application/json" \
  -d '{
    "id": "vllm/mistral-7b-instruct",
    "provider": "vLLM",
    "family": "Mistral",
    "version": "7b-instruct",
    "is_custom": true,
    "capabilities": {
      "context_window": 32768,
      "max_output_tokens": 4096,
      "vision": false,
      "tool_use": true,
      "structured_output": true,
      "streaming": true,
      "parallel_tool_calls": false,
      "extended_thinking": false
    },
    "characteristics": {
      "reasoning_depth": "medium",
      "instruction_following": "medium",
      "code_generation": "medium",
      "latency_tier": "low"
    },
    "pricing": {
      "input_per_1m_tokens": 0.0,
      "output_per_1m_tokens": 0.0
    },
    "api": {
      "endpoint": "http://localhost:8000/v1",
      "auth_type": "none",
      "sdk": ["openai"],
      "openai_compat": true
    }
  }'
```

#### 로컬 모델 자동 검색 API (편의 기능)

Ollama가 실행 중이면 설치된 모델 목록을 스캔하여 레지스트리에 일괄 등록한다.

```
POST /models/import/ollama
  Body: { "base_url": "http://localhost:11434", "auto_register": true }

Response:
{
  "imported": ["ollama/llama3.2:3b", "ollama/qwen2.5:7b"],
  "already_registered": ["ollama/mistral:7b"],
  "failed": []
}
```

```python
# model_registry_service/importers/ollama_importer.py

async def import_from_ollama(base_url: str, db: AsyncSession) -> dict:
    adapter = OllamaAdapter(model_name="", base_url=base_url)

    if not await adapter.health_check():
        raise ConnectionError(f"Ollama에 연결할 수 없습니다: {base_url}")

    installed = await adapter.list_local_models()
    results = {"imported": [], "already_registered": [], "failed": []}

    for model_name in installed:
        model_id = f"ollama/{model_name}"
        existing = await db.get(ModelRegistry, model_id)
        if existing:
            results["already_registered"].append(model_id)
            continue
        try:
            meta = _infer_model_meta(model_name)  # 이름에서 컨텍스트 크기 등 추정
            db.add(ModelRegistry(
                id=model_id,
                provider="Ollama",
                family=meta["family"],
                version=meta["version"],
                is_custom=True,
                capabilities=meta["capabilities"],
                characteristics=meta["characteristics"],
                pricing={"input_per_1m_tokens": 0.0, "output_per_1m_tokens": 0.0},
                api_config={"endpoint": base_url, "auth_type": "none",
                            "model_name": model_name, "openai_compat": True},
            ))
            results["imported"].append(model_id)
        except Exception as e:
            results["failed"].append({"model": model_id, "error": str(e)})

    await db.commit()
    return results


# 모델명에서 기본 메타 추정 (실제 구현 시 Ollama 모델 라이브러리 API 활용 권장)
_FAMILY_PATTERNS = [
    ("llama", {"family": "Llama", "reasoning_depth": "medium"}),
    ("mistral", {"family": "Mistral", "reasoning_depth": "medium"}),
    ("qwen", {"family": "Qwen", "reasoning_depth": "medium"}),
    ("deepseek", {"family": "DeepSeek", "reasoning_depth": "high"}),
    ("phi", {"family": "Phi", "reasoning_depth": "medium"}),
    ("gemma", {"family": "Gemma", "reasoning_depth": "medium"}),
]

def _infer_model_meta(model_name: str) -> dict:
    name_lower = model_name.lower()
    family = "Unknown"
    reasoning_depth = "medium"
    for pattern, meta in _FAMILY_PATTERNS:
        if pattern in name_lower:
            family = meta["family"]
            reasoning_depth = meta["reasoning_depth"]
            break

    # 파라미터 크기로 컨텍스트 윈도우 추정
    context_window = 8192
    if any(x in name_lower for x in ["70b", "72b", "34b", "32b"]):
        context_window = 131072
    elif any(x in name_lower for x in ["13b", "14b"]):
        context_window = 32768
    elif any(x in name_lower for x in ["7b", "8b"]):
        context_window = 32768

    return {
        "family": family,
        "version": model_name,
        "capabilities": {
            "context_window": context_window,
            "max_output_tokens": min(context_window // 4, 8192),
            "vision": "vision" in name_lower or "vl" in name_lower,
            "tool_use": True,
            "structured_output": True,
            "streaming": True,
            "parallel_tool_calls": False,
            "extended_thinking": False,
        },
        "characteristics": {
            "reasoning_depth": reasoning_depth,
            "instruction_following": "medium",
            "code_generation": "medium",
            "latency_tier": "low",
        },
    }
```

---

### 8.4 로컬 모델을 포함한 비교 태스크 실행

로컬 모델은 클라우드 모델과 동일한 비교 태스크 API를 사용한다. 단, 아래 차이를 주의한다.

#### 비교 태스크 예시 (클라우드 + 로컬 혼합)

```bash
curl -X POST http://localhost:8003/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Cloud vs Local Benchmark",
    "artifact_id": "agent-v2.3",
    "models": [
      "claude-sonnet-4-6",
      "gpt-4o",
      "ollama/llama3.2:3b",
      "vllm/mistral-7b-instruct"
    ],
    "dataset_id": "eval-set-finance-001",
    "metrics": ["correctness", "tool_call_accuracy", "latency_p95", "cost_per_query"]
  }'
```

#### 로컬 모델 실행 전 가용성 체크

비교 태스크 실행 전 모든 모델의 health_check를 수행하여 로컬 모델이 기동 중인지 확인한다.

```python
# comparison_engine/runner.py

async def preflight_check(model_ids: list[str]) -> dict:
    """태스크 실행 전 모든 모델 어댑터 연결 확인"""
    results = {}
    checks = await asyncio.gather(*[
        _check_single(model_id) for model_id in model_ids
    ], return_exceptions=True)
    for model_id, ok in zip(model_ids, checks):
        results[model_id] = ok if isinstance(ok, bool) else False
    return results

async def _check_single(model_id: str) -> bool:
    adapter = get_adapter(model_id)
    return await adapter.health_check()

async def run_comparison_task(task: ComparisonTask) -> list[ComparisonResult]:
    # 실행 전 가용성 체크
    availability = await preflight_check(task.model_ids)
    unavailable = [m for m, ok in availability.items() if not ok]
    if unavailable:
        raise RuntimeError(
            f"다음 모델에 연결할 수 없습니다: {unavailable}\n"
            f"로컬 모델은 Ollama/vLLM 서버가 실행 중인지 확인하세요."
        )

    dataset = await load_dataset(task.dataset_id)
    results = await asyncio.gather(*[
        evaluate_model(model_id, task, dataset)
        for model_id in task.model_ids
    ], return_exceptions=True)
    return [r for r in results if not isinstance(r, Exception)]
```

#### 비용 계산 — 로컬 모델은 0원 처리

```python
# comparison_engine/cost.py

def calculate_cost(model_id: str, usage: dict) -> float:
    model = model_registry.get(model_id)
    # 로컬 모델(pricing 0.0)은 비용 없음
    input_cost = (usage["input_tokens"] / 1_000_000
                  * model.pricing["input_per_1m_tokens"])
    output_cost = (usage["output_tokens"] / 1_000_000
                   * model.pricing["output_per_1m_tokens"])
    return input_cost + output_cost
```

리포트에서 로컬 모델은 비용 0으로 표시되며, 비용-성능 산점도에서 별도 색상(예: 녹색)으로 구분한다.

---

### 8.5 도구 형식 호환성 처리

클라우드 모델(Anthropic)과 로컬 모델(OpenAI-compat)은 도구 스키마 형식이 다르다. 비교 엔진이 어댑터에 전달하기 전에 자동 변환한다.

```python
# llm_adapter/tool_converter.py

def convert_tools_for_adapter(
    tools: list[dict],
    target_format: str,   # "anthropic" | "openai"
) -> list[dict]:
    if target_format == "openai":
        return [_anthropic_to_openai(t) for t in tools]
    return tools  # Anthropic 형식이 내부 표준

def _anthropic_to_openai(tool: dict) -> dict:
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": tool.get("input_schema", {}),
        },
    }

def _openai_to_anthropic(tool: dict) -> dict:
    fn = tool["function"]
    return {
        "name": fn["name"],
        "description": fn.get("description", ""),
        "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
    }
```

내부 표준 형식은 **Anthropic 스키마**로 통일하고, OpenAI-compat 어댑터로 전송 시에만 변환한다.

---

### 8.6 로컬 모델 운영 시 주의사항

| 항목 | 내용 |
|------|------|
| **타임아웃** | 로컬 GPU/CPU 속도에 따라 응답 시간이 클라우드 대비 수~수십 배 느릴 수 있다. 어댑터 타임아웃을 120초 이상으로 설정한다. |
| **동시 요청** | 로컬 모델은 단일 인스턴스가 많으므로 병렬 실행 시 큐잉이 발생한다. 비교 태스크의 `max_concurrent_local` 파라미터로 동시 요청 수를 제한한다. |
| **메모리** | 대형 모델(7B+)은 VRAM/RAM 부족 시 비정상 응답이 나올 수 있다. health_check 외에 첫 요청을 워밍업으로 실행 권장. |
| **모델 버전** | 동일 이름이라도 Ollama 모델은 업데이트될 수 있다. 비교 재현성을 위해 태스크 결과에 `ollama/llama3.2:3b@sha256:...` 형태의 다이제스트를 함께 저장한다. |
| **도구 호출 지원** | 모든 로컬 모델이 도구 호출을 지원하지 않는다. 레지스트리의 `capabilities.tool_use` 값을 실제로 확인하고, 지원하지 않는 모델에 도구 평가 태스크를 실행하면 오류 대신 경고 후 건너뛴다. |

---

### 8.7 Docker Compose — 로컬 LLM 포함 전체 스택

```yaml
# docker-compose.yml (로컬 개발용)
services:
  postgres:
    image: timescale/timescaledb:latest-pg16
    environment:
      POSTGRES_DB: llm_mgmt
      POSTGRES_USER: llm_mgmt
      POSTGRES_PASSWORD: password
    ports: ["5432:5432"]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    ports: ["9000:9000", "9001:9001"]

  ollama:
    image: ollama/ollama:latest
    ports: ["11434:11434"]
    volumes:
      - ollama_data:/root/.ollama
    # GPU 사용 시 (NVIDIA)
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  # Ollama 초기 모델 다운로드 (최초 1회)
  ollama-init:
    image: ollama/ollama:latest
    depends_on: [ollama]
    entrypoint: >
      sh -c "
        sleep 5 &&
        ollama pull llama3.2:3b &&
        ollama pull qwen2.5:7b
      "
    environment:
      OLLAMA_HOST: http://ollama:11434

volumes:
  ollama_data:
```

GPU 없이 CPU만 사용하는 경우 `deploy` 블록을 제거하고 소형 모델(1B~3B)을 사용한다.

---

## 9. 테스트 전략

### 8.1 테스트 계층

```
unit/               # 비즈니스 로직 단위 테스트 (mocking 없이)
  test_dependency_analyzer.py
  test_metrics_calculator.py
  test_recommender.py
integration/        # DB, 외부 API 통합 테스트
  test_artifact_crud.py
  test_model_registry.py
  test_comparison_task_flow.py
e2e/                # 전체 플로우 테스트
  test_model_upgrade_scenario.py  # 사용자 시나리오 1
  test_aiops_incident_response.py # 사용자 시나리오 2
```

### 8.2 핵심 테스트 케이스

**의존성 분석기 테스트**

```python
def test_tool_choice_required_detected():
    analyzer = ArtifactDependencyAnalyzer()
    content = {"tool_choice": "required", "tools": [...]}
    deps = analyzer.analyze("mcp", content)
    assert any(d.feature == "tool_choice_required" for d in deps)

def test_incompatible_model_detected():
    analyzer = ArtifactDependencyAnalyzer()
    deps = [ModelDependency("vision", required=True, description="...")]
    capabilities = {"vision": False, "tool_use": True}
    assert analyzer.check_compatibility(deps, capabilities) == CompatibilityLevel.INCOMPATIBLE
```

**비교 엔진 테스트**

```python
@pytest.mark.asyncio
async def test_parallel_evaluation_runs_all_models(mock_llm_adapter):
    task = ComparisonTask(model_ids=["model-a", "model-b", "model-c"], ...)
    results = await run_comparison_task(task)
    assert len(results) == 3
    assert all(r.metrics for r in results)
```

### 8.3 LLM API 호출 비용 절감

테스트 시 실제 LLM API 호출은 최소화한다.

- **단위/통합 테스트**: `pytest-recording` + VCR cassette로 응답 녹화·재생
- **E2E 테스트**: 소규모 데이터셋(5~10개 케이스)으로 실행, CI에서는 비활성화

---

## 10. Phase별 개발 체크리스트

### Phase 1 — 기반 구축 (1~6주)

- [ ] Docker Compose 로컬 환경 구성 (PostgreSQL, Redis, MinIO, Ollama)
- [ ] Alembic 마이그레이션 설정 및 초기 스키마 적용
- [ ] LLM 어댑터 레이어 구현 (Anthropic, OpenAI, OllamaAdapter, OpenAICompatAdapter)
- [ ] 어댑터 팩토리 및 도구 형식 변환기 구현
- [ ] `artifact-service`: 에이전트·아티팩트 CRUD (FR-A1)
- [ ] `artifact-service`: 의존성 분석기 구현 (FR-A2)
- [ ] `model-registry-service`: 모델 CRUD (FR-B1)
- [ ] `model-registry-service`: 로컬 모델 자동 검색 API (`POST /models/import/ollama`)
- [ ] `model-registry-service`: 비교 매트릭스 API (FR-B2)
- [ ] API 키 암호화 저장 구현 (로컬 모델은 키 없음 처리)
- [ ] OpenAPI 문서 자동 생성 확인
- [ ] 단위 테스트 커버리지 80% 이상

**완료 기준**: 아티팩트 등록 → 의존성 분석 → 모델 호환성 조회 플로우 동작

---

### Phase 2 — 비교 분석 엔진 (7~12주)

- [ ] 비교 태스크 스키마 및 CRUD (FR-C1)
- [ ] Celery worker 설정, 태스크 큐 구현
- [ ] 태스크 실행 전 preflight_check (로컬 모델 가용성 포함) 구현
- [ ] 병렬 모델 평가 실행기 구현 (FR-C2, `max_concurrent_local` 옵션)
- [ ] 로컬 모델 타임아웃 및 동시 요청 수 제한 처리
- [ ] WebSocket 진행 상태 실시간 전달
- [ ] 지표 계산 모듈 구현 (FR-C3, 로컬 모델 비용 = 0 처리)
- [ ] 결과 리포트에 로컬/클라우드 구분 시각화 (비용-성능 산점도 색상 분리)
- [ ] 결과 S3 저장 — 로컬 모델 모델 다이제스트(버전) 함께 저장
- [ ] 권장 모델 제안 로직 (FR-C4)
- [ ] A/B 비교 뷰 API (FR-C5)
- [ ] 비용 캡 설정 (클라우드 모델만 적용, 로컬 모델은 타임아웃으로 제한)
- [ ] 통합 테스트: 클라우드 + 로컬 혼합 3개 이상 모델 동시 비교

**완료 기준**: 3개 이상 모델 동시 비교 → 리포트 자동 생성

---

### Phase 3 — AIOps + AI 에이전트 (13~20주)

- [ ] TimescaleDB 설정 및 지표 수집 API (FR-D1)
- [ ] 이상 탐지 알고리즘 구현 (FR-D2)
- [ ] 알림 시스템 (이메일, 웹훅)
- [ ] AI 진단 에이전트 구현 — Claude SDK (FR-D3)
- [ ] 조치 승인 플로우 API
- [ ] 자동화 규칙 엔진 구현 (FR-D4)
- [ ] 고위험 조치 인간 승인 필수화
- [ ] 일간/주간 운영 리포트 자동 생성 (FR-D5)
- [ ] 감사 로그 (모든 조치 이력 1년 보존)
- [ ] E2E 테스트: 이상 감지 → AI 진단 → 승인 → 자동 조치

**완료 기준**: 전체 AIOps 플로우 동작

---

## 11. 운영 가이드

### 10.1 모니터링 항목

| 서비스 | 핵심 지표 |
|--------|-----------|
| comparison-engine | 태스크 큐 깊이, 실행 중 태스크 수, API 오류율 |
| aiops-service | 이상 감지 건수, 오탐율, MTTD |
| llm-adapter | 공급자별 API 오류율, 레이턴시 P95 |
| 전체 | API 게이트웨이 RPS, 오류율 |

### 10.2 보안 체크리스트

- [ ] 모든 API 키 `ENCRYPTION_KEY`로 암호화 후 DB 저장 (평문 저장 금지)
- [ ] RBAC: 역할별 접근 범위 정의 (개발자 / ML 엔지니어 / AIOps 엔지니어 / 관리자)
- [ ] 고위험 자동 조치(`requires_approval: true`)는 반드시 인간 승인 후 실행
- [ ] 민감 프롬프트 데이터는 전송 전 마스킹 옵션 제공
- [ ] 모든 LLM API 호출에 비용 캡 적용 (비교 태스크당 최대 USD)

### 10.3 비용 관리

```python
# 비교 태스크 실행 전 예상 비용 계산
def estimate_task_cost(task: ComparisonTask, dataset: list) -> float:
    total = 0.0
    for model_id in task.model_ids:
        model = model_registry.get(model_id)
        avg_input_tokens = sum(count_tokens(c.input_messages) for c in dataset) / len(dataset)
        avg_output_tokens = 500  # 추정치
        cost = (avg_input_tokens / 1_000_000 * model.pricing["input_per_1m_tokens"]
                + avg_output_tokens / 1_000_000 * model.pricing["output_per_1m_tokens"])
        total += cost * len(dataset)
    return total
```

---

## 부록

### A. 커스텀 모델 어댑터 추가 방법 (FR-B4)

**OpenAI-compatible API를 노출하는 경우 (권장)**

모델 레지스트리 등록 시 `api.openai_compat: true`와 `api.endpoint`만 설정하면 `OpenAICompatAdapter`가 자동으로 사용된다. 별도 코드 불필요.

**완전 커스텀 API인 경우**

1. `llm_adapter/` 에 `{provider}_adapter.py` 파일 생성
2. `BaseLLMAdapter`를 상속하여 `complete()`와 `health_check()` 구현
3. `get_adapter()` 팩토리의 `match` 블록에 공급자 조건 추가
4. 모델 레지스트리에 등록 시 `is_custom: true`, `provider: "{신규 공급자명}"` 지정

**Ollama 신규 모델 추가**

코드 변경 없이 `POST /models/import/ollama`로 자동 등록하거나,  
`ollama pull {model_name}` 후 레지스트리에 수동 등록한다.

### B. 평가 데이터셋 포맷

```json
{
  "id": "eval-set-finance-001",
  "cases": [
    {
      "id": "case-001",
      "input_messages": [
        {"role": "user", "content": "2023년 4분기 매출을 조회해줘"}
      ],
      "tools": [...],
      "expected_output": "...",
      "expected_tool_calls": [
        {"name": "query_sales", "arguments": {"year": 2023, "quarter": 4}}
      ]
    }
  ]
}
```

### C. 환경별 설정

| 환경 | DB | LLM API | 비용 캡 |
|------|----|---------|---------|
| local | Docker PostgreSQL | VCR cassette | 없음 |
| staging | RDS (소형) | 실제 API (소규모 데이터셋) | $5/태스크 |
| production | RDS (다중AZ) | 실제 API | 설정 가능 |
