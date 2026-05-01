# LLM Management System

> **LLM-Aware** 에이전트 관리 시스템 — 모델 레지스트리, 다모델 비교 분석, AIOps 자동 대응

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 개요

AI 에이전트 개발에서 LLM 모델을 교체할 때마다 프롬프트·MCP 설정·Skills이 의도대로 동작하지 않는 문제를 해결하기 위한 **LLM-aware(모델 인지형)** 관리 플랫폼입니다.

```
┌──────────────────────────────────────────────────────┐
│                    Web UI / CLI                       │
└─────────────────────┬────────────────────────────────┘
                      │ REST API / WebSocket
┌─────────────────────▼────────────────────────────────┐
│                  API Gateway                          │
└──┬──────────┬──────────┬──────────────┬──────────────┘
   │          │          │              │
┌──▼──┐  ┌───▼───┐  ┌───▼────┐  ┌──────▼──────┐
│  A  │  │   B   │  │   C    │  │     D        │
│Agent│  │Model  │  │Compare │  │  AIOps       │
│Mgmt │  │Reg.   │  │Engine  │  │  + AI Agent  │
└─────┘  └───────┘  └────────┘  └─────────────┘
              LLM Adapter Layer
   Anthropic │ OpenAI │ Ollama │ vLLM │ LM Studio
```

---

## 주요 기능

| 모듈 | 기능 |
|------|------|
| **A. 에이전트 관리** | 아티팩트(프롬프트·MCP·Skills) 등록·버전 관리, 모델 의존성 자동 분석, 전환 영향 분석 |
| **B. 모델 레지스트리** | 클라우드·로컬 모델 등록, 특성 비교 매트릭스, 생명주기 관리, Ollama 자동 탐색 |
| **C. 비교 분석 엔진** | 병렬 다모델 평가, 7가지 지표 계산, 권장 모델 제안, 실시간 WebSocket 진행 로그, 평가 데이터셋 관리, 상세 평가 내역 (Transparency Log) |
| **D. AIOps** | 운영 지표 수집, 이상 탐지, AI 에이전트 자동 진단·조치, 승인 플로우, 규칙 엔진 |

---

## 지원 LLM

| 유형 | 공급자 |
|------|--------|
| **클라우드** | Anthropic (Claude), OpenAI (GPT), Google (Gemini) |
| **로컬** | Ollama, vLLM, LM Studio, LocalAI |
| **커스텀** | OpenAI-compatible API를 노출하는 모든 서버 |

---

## 빠른 시작

### 사전 요구사항
- Docker & Docker Compose
- Python 3.12+
- (선택) Ollama — 로컬 LLM 비교 시

### 1. 저장소 클론

```bash
git clone https://github.com/lesh915/llm-management.git
cd llm-management
```

### 2. 환경 변수 설정

```bash
cp .env.example .env
# .env 파일에서 API 키 입력 (Anthropic, OpenAI 등 사용하는 공급자만)
```

### 3. 전체 스택 실행

```bash
docker compose up -d
```

서비스 포트:

| 서비스 | URL | 역할 |
|--------|-----|------|
| **Web UI** | http://localhost:47001 | 관리 대시보드 |
| **API Gateway** | http://localhost:47000/docs | 통합 진입점 (모든 API) |
| artifact-service | http://localhost:47010/docs | 에이전트 아티팩트 관리 |
| model-registry-service | http://localhost:47011/docs | LLM 모델 레지스트리 |
| comparison-engine | http://localhost:47012/docs | 다모델 비교 분석 |
| aiops-service | http://localhost:47013/docs | AIOps 모니터링 |
| ai-agent-runner | http://localhost:47014/docs | AI 진단 에이전트 |
| MinIO API | http://localhost:47002 | 오브젝트 스토리지 API |
| MinIO Console | http://localhost:47003 | 오브젝트 스토리지 UI |
| Celery Flower | http://localhost:47004 | 비교 태스크 모니터링 |

> **API Gateway를 통한 접근**: 모든 API는 `http://localhost:47000`으로 통합 접근 가능합니다.

### 4. (선택) 로컬 Ollama 모델 자동 등록

```bash
# Ollama가 실행 중인 경우 — 설치된 모델을 레지스트리에 자동 등록
curl -X POST http://localhost:47011/models/import/ollama \
  -H "Content-Type: application/json" \
  -d '{"base_url": "http://localhost:11434"}'
```

---

## 사용 예시

### 클라우드 + 로컬 모델 비교

```bash
# 1. 클라우드 모델 등록
curl -X POST http://localhost:47011/models \
  -H "Content-Type: application/json" \
  -d '{
    "id": "claude-sonnet-4-6",
    "provider": "Anthropic",
    "family": "Claude 4",
    "version": "4.6",
    "capabilities": {
      "context_window": 200000, "max_output_tokens": 8192,
      "vision": true, "tool_use": true, "structured_output": true,
      "streaming": true, "parallel_tool_calls": true, "extended_thinking": false
    },
    "characteristics": {
      "reasoning_depth": "high", "instruction_following": "high",
      "code_generation": "high", "latency_tier": "medium"
    },
    "pricing": {"input_per_1m_tokens": 3.0, "output_per_1m_tokens": 15.0},
    "api": {"endpoint": "https://api.anthropic.com/v1", "auth_type": "api_key"}
  }'

# 2. 비교 태스크 생성 (클라우드 + 로컬 혼합)
curl -X POST http://localhost:47012/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Cloud vs Local Benchmark",
    "models": ["claude-sonnet-4-6", "ollama/llama3.2:3b"],
    "dataset_id": "my-eval-set",
    "metrics": ["correctness", "tool_call_accuracy", "latency_p95", "cost_per_query"]
  }'

# 3. 태스크 실행
curl -X POST http://localhost:47012/tasks/{task_id}/run

# 4. 결과 리포트 조회
curl http://localhost:47012/tasks/{task_id}/report

# 5. 권장 모델 조회 (비용 우선)
curl "http://localhost:47012/tasks/{task_id}/recommendation?priority=cost"
```

### 모델 전환 영향 분석

```bash
# 아티팩트 등록
curl -X POST http://localhost:47010/agents/{agent_id}/artifacts \
  -H "Content-Type: application/json" \
  -d '{
    "type": "mcp",
    "content": {"tool_choice": "required", "tools": [...]}
  }'

# 영향 분석 (claude-sonnet → ollama/llama3.2:3b 전환 시)
curl "http://localhost:47010/artifacts/{artifact_id}/impact\
?source_model_id=claude-sonnet-4-6&target_model_id=ollama/llama3.2:3b"
```

---

## 프로젝트 구조

```
llm-management/
├── services/
│   ├── api-gateway/               # 통합 진입점 — JWT 인증, 역방향 프록시
│   ├── artifact-service/          # 모듈 A — 에이전트 아티팩트 관리
│   ├── model-registry-service/    # 모듈 B — LLM 모델 레지스트리
│   ├── comparison-engine/         # 모듈 C — 다모델 비교 분석
│   ├── aiops-service/             # 모듈 D — AIOps 모니터링
│   ├── ai-agent-runner/           # 모듈 D — AI 진단 에이전트 (Claude SDK)
│   └── llm-adapter/               # 공통 — LLM 어댑터 레이어
├── packages/
│   └── shared-types/              # 공유 ORM 모델 + Pydantic 스키마
├── infra/
│   ├── migrations/                # Alembic DB 마이그레이션
│   └── k8s/                       # Kubernetes 매니페스트
├── web/                               # Next.js 15 Web UI 대시보드
├── docker-compose.yml
├── .env.example
├── LLM-PRD.md                     # 제품 요구사항 문서
└── DEVELOPMENT_GUIDE.md           # 개발 가이드 (v1.1.0)
```

---

## 개발 로드맵

| Phase | 내용 | 상태 |
|-------|------|------|
| **Phase 1** | 에이전트 아티팩트 관리 (모듈 A) + 모델 레지스트리 (모듈 B) + LLM 어댑터 레이어 | ✅ 완료 |
| **Phase 2** | 다모델 비교 분석 엔진 (모듈 C) + Celery 병렬 실행 + WebSocket | ✅ 완료 |
| **Phase 3** | AIOps 모니터링 + AI 에이전트 자동 진단·조치 (모듈 D) | ✅ 완료 |
| **Phase 4** | API Gateway + LLM 어댑터 테스트 + Alembic 설정 + Kubernetes 매니페스트 | ✅ 완료 |
| **Phase 5** | Next.js 15 Web UI — 대시보드, 모델 레지스트리, 비교 분석, AIOps 모니터링 | ✅ 완료 |

---

## API 문서

모든 API는 **API Gateway** (`http://localhost:8000/docs`)를 통해 통합 접근하거나 각 서비스 Swagger UI에서 직접 확인할 수 있습니다.

| 서비스 | Swagger UI |
|--------|-----------|
| API Gateway (통합) | http://localhost:47000/docs |
| Artifact Service | http://localhost:47010/docs |
| Model Registry | http://localhost:47011/docs |
| Comparison Engine | http://localhost:47012/docs |
| AIOps Service | http://localhost:47013/docs |
| AI Agent Runner | http://localhost:47014/docs |

---

## 테스트 실행

```bash
# 에이전트 아티팩트 단위 테스트
pytest services/artifact-service/tests/ -v

# 모델 레지스트리 단위 테스트
pytest services/model-registry-service/tests/ -v

# 비교 엔진 단위 테스트 (지표, 추천, 비용 — 총 33개)
pytest services/comparison-engine/tests/ -v

# AIOps 규칙 엔진 단위 테스트
pytest services/aiops-service/tests/ -v

# AI 진단 에이전트 단위 테스트
pytest services/ai-agent-runner/tests/ -v

# LLM 어댑터 단위 테스트 (어댑터, 팩토리, 도구 변환)
pytest services/llm-adapter/tests/ -v

# 전체 테스트 일괄 실행
pytest services/ -v --tb=short
```

---

## 기여

1. `main` 브랜치에서 feature 브랜치 생성
2. 변경 사항 구현 및 테스트 작성
3. PR 생성 — 제목·본문 규칙은 기존 PR 참고

---

## 라이선스

MIT License © 2026 Seungha Lee
