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
   Anthropic │ OpenAI │ Google │ Ollama │ vLLM │ LM Studio
```

---

## 주요 기능

| 모듈 | 기능 |
|------|------|
| **A. 에이전트 관리** | 아티팩트(프롬프트·MCP·Skills) 등록·버전 관리, 모델 의존성 자동 분석, 전환 영향 분석 |
| **B. 모델 레지스트리** | 클라우드·로컬 모델 등록, 특성 비교 매트릭스, 생명주기 관리, 영구 삭제 및 연쇄 삭제(Cascade), Ollama 자동 탐색 |
| **C. 비교 분석 엔진** | 병렬 다모델 평가, 7가지 지표 계산, 권장 모델 제안, 실시간 WebSocket 진행 로그, 에러 원인 추적 및 상세 로그 (Transparency Log), 평가 데이터셋 관리 |
| **D. AIOps** | 운영 지표 수집, 이상 탐지, AI 에이전트 자동 진단·조치, 승인 플로우, 규칙 엔진 |

---

## 지원 LLM (2026.05 기준)

| 유형 | 공급자 | 주요 모델 |
|------|--------|-----------|
| **클라우드** | Anthropic | Claude 4.7 Opus, 4.6 Sonnet, 4.5 Haiku |
| **클라우드** | Google | Gemini 3.1 Pro, 3 Flash (Preview) |
| **클라우드** | OpenAI | GPT-4o, GPT-4o-mini |
| **로컬** | Ollama, vLLM | Llama 3.2, Qwen 2.5, DeepSeek V3 등 |

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

---

## 사용 예시

### 클라우드 + 로컬 모델 비교

```bash
# 1. 클라우드 모델 등록 (2026.05 프리셋 활용 권장)
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

# 2. 비교 태스크 생성
curl -X POST http://localhost:47012/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Benchmark 2026 Q2",
    "models": ["claude-sonnet-4-6", "ollama/llama3.2:3b"],
    "dataset_id": "my-eval-set",
    "metrics": ["correctness", "latency_p95", "cost_per_query"]
  }'
```

---

## 신뢰성 및 진단 기능

- **에러 투명성 (Transparency Log)**: 비교 분석 태스크 실패 시, 단순히 'failed' 상태만 표시하는 것이 아니라 API 호출 오류, 인증 실패, 모델 ID 미존재 등 상세 원인을 캡처하여 UI에 직접 출력합니다.
- **모델 관리 유연성**: 2026년 최신 모델 카탈로그를 지원하며, 모델 영구 삭제 시 관련 데이터를 자동으로 정리하는 연쇄 삭제(Cascade Delete) 기능을 통해 관리 편의성을 강화했습니다.
- **WebSocket 상태 동기화**: 백엔드 엔진과 프론트엔드 간의 실시간 통신을 개선하여, 태스크 성공/실패 시 즉시 웹소켓 세션을 정리하고 리포트를 자동 노출합니다.
- **데이터 무결성 및 보안**: 엔진이 DB에서 직접 암호화된 인증 정보를 조회하는 아키텍처를 적용하여, API Gateway의 보안 정책(마스킹)과 상관없이 안정적인 모델 호출이 가능합니다.
- **환경 변수 폴백**: DB에 API 키를 등록하지 않더라도 시스템 환경 변수(`.env`)에 설정된 키를 자동으로 탐색하여 유연하게 동작합니다.

---

## 라이선스

MIT License © 2026 Seungha Lee
