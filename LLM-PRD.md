# LLM Management System — Product Requirements Document

**버전**: 1.0.0  
**작성일**: 2026-04-24  
**상태**: Draft

---

## 1. 개요 (Overview)

### 1.1 배경 및 문제 정의

AI 에이전트 개발 과정에서 LLM 모델 변경은 불가피하게 발생한다. 모델이 교체될 때마다 기존에 작성한 프롬프트, MCP(Model Context Protocol) 설정, Skills 등이 의도대로 동작하지 않는 문제가 반복된다. 현재 이를 해결하는 체계적인 도구가 없어 개발자는 매번 수동으로 검증하고 수정해야 한다.

핵심 문제는 기존 에이전트 개발 방식이 **LLM-agnostic**(모델 무관) 설계를 지향하지만, 실제 현장에서는 특정 모델의 특성—컨텍스트 윈도우 크기, 도구 호출 방식, 추론 깊이, 응답 포맷 등—에 크게 의존한다는 점이다. 이 간극을 줄이기 위해 **LLM-aware(모델 인지형)** 설계 방법론을 중심으로 한 관리 시스템이 필요하다.

### 1.2 목표

- 에이전트 구성 요소(프롬프트, MCP, Skills)를 모델별로 분석·관리
- LLM 모델 레지스트리를 통해 모델 특성 정보를 구조화
- 다모델 비교 분석 파이프라인을 제공하여 최적 모델 선택 지원
- AIOps 기능을 AI 에이전트와 협력하여 자동화

### 1.3 범위

| 포함 | 제외 |
|------|------|
| 에이전트 구성 분석 및 버전 관리 | LLM 모델 학습/파인튜닝 |
| LLM 모델 메타데이터 레지스트리 | 클라우드 인프라 프로비저닝 |
| 비교 평가 실행 및 결과 저장 | 프롬프트 자동 생성 |
| AIOps 대시보드 및 알림 | 엔드유저 챗봇 UI |

---

## 2. 사용자 및 이해관계자 (Stakeholders)

| 역할 | 설명 | 주요 니즈 |
|------|------|-----------|
| **AI 에이전트 개발자** | 에이전트를 설계·구현하는 주 사용자 | 모델 전환 시 영향 범위 파악, 빠른 검증 |
| **ML 엔지니어** | 모델 성능 평가·최적화 담당 | 정량 비교 지표, 자동화된 벤치마크 |
| **AIOps 엔지니어** | 운영 모니터링 담당 | 이상 탐지, 자동 롤백, 알림 |
| **기술 리더** | 아키텍처 의사결정 | 비용·성능 트레이드오프 가시성 |

---

## 3. 핵심 개념 (Core Concepts)

### 3.1 LLM-Aware 설계 원칙

기존 LLM-agnostic 접근은 "어떤 모델이든 동일하게 동작해야 한다"는 전제를 둔다. 본 시스템은 반대 전제에서 출발한다.

> **모델마다 최적의 도구 설계가 다르며, 이를 명시적으로 관리해야 한다.**

| 관점 | LLM-Agnostic | LLM-Aware |
|------|-------------|-----------|
| 프롬프트 | 단일 버전 유지 | 모델별 변형(variant) 관리 |
| 도구 정의 | 공통 스키마 강제 | 모델 특성에 맞게 파라미터 조정 |
| 평가 기준 | 범용 벤치마크 | 모델×태스크 조합별 맞춤 지표 |
| 운영 | 단일 배포 파이프라인 | 모델 특화 배포 프로파일 |

### 3.2 에이전트 구성 요소 (Agent Artifact)

```
Agent
├── Prompts          # System / User / Assistant 프롬프트
├── MCP Configs      # 도구 정의, 서버 설정
├── Skills           # 재사용 가능한 기능 모듈
├── Tool Schemas     # 함수 시그니처, 파라미터 설명
└── Evaluation Sets  # 예상 입출력 쌍
```

---

## 4. 기능 요구사항 (Functional Requirements)

### 4.1 모듈 A — 에이전트 구성 분석 및 관리

#### FR-A1: 에이전트 아티팩트 등록
- 사용자는 프롬프트, MCP 설정 파일, Skills 정의를 시스템에 등록할 수 있다.
- 등록 시 자동으로 구성 요소를 파싱하여 메타데이터(토큰 수 추정, 도구 호출 패턴, 의존 모델 기능)를 추출한다.
- 아티팩트는 버전 관리되며 변경 이력이 기록된다.

#### FR-A2: 모델 의존성 분석
- 각 아티팩트를 분석하여 **모델 특화 기능 의존성**을 자동 감지한다.
  - 예: `tool_choice: "required"`, 긴 컨텍스트 윈도우, 구조화 출력(JSON mode), vision 입력 등
- 분석 결과는 "호환 가능", "부분 호환", "비호환" 세 단계로 표시된다.

#### FR-A3: 모델 전환 영향 분석 (Impact Analysis)
- 사용자가 현재 모델에서 대상 모델로 전환 시 영향받는 구성 요소 목록을 제공한다.
- 각 구성 요소에 대한 수정 필요 사항 및 권장 변경안을 제시한다.

#### FR-A4: 모델별 프롬프트 변형 관리
- 단일 프롬프트에 대해 여러 모델 최적화 변형(variant)을 연결하여 관리한다.
- 변형 간 diff 뷰 제공.

---

### 4.2 모듈 B — LLM 모델 레지스트리

#### FR-B1: 모델 등록
- 사용자는 LLM 모델을 시스템에 등록할 수 있다.
- 등록 정보:

```yaml
model:
  id: "claude-sonnet-4-6"
  provider: "Anthropic"
  family: "Claude 4"
  version: "4.6"
  
capabilities:
  context_window: 200000       # tokens
  max_output_tokens: 8192
  vision: true
  tool_use: true
  structured_output: true      # JSON mode
  streaming: true
  parallel_tool_calls: true
  extended_thinking: false
  
characteristics:
  reasoning_depth: "high"      # low / medium / high
  instruction_following: "high"
  code_generation: "high"
  latency_tier: "medium"       # low / medium / high
  
pricing:
  input_per_1m_tokens: 3.00    # USD
  output_per_1m_tokens: 15.00  # USD
  
api:
  endpoint: "https://api.anthropic.com/v1"
  auth_type: "api_key"
  sdk: ["anthropic-python", "anthropic-js"]
```

#### FR-B2: 모델 특성 비교 매트릭스
- 등록된 모델 간 특성을 표 형태로 비교한다.
- 필터: Provider, 기능(vision, tool_use 등), 비용 범위, 컨텍스트 크기.

#### FR-B3: 모델 상태 관리
- 모델의 생명주기 상태를 관리한다: `active` → `deprecated` → `retired`
- deprecated 알림: 해당 모델을 사용 중인 에이전트 아티팩트 소유자에게 통지.

#### FR-B4: 커스텀 모델 지원
- 자체 호스팅(ollama, vLLM 등) 또는 파인튜닝된 모델도 등록 가능하다.
- 표준 OpenAI-compatible API 규격 또는 커스텀 어댑터를 통해 연결.

---

### 4.3 모듈 C — 다모델 비교 분석

#### FR-C1: 비교 분석 태스크 정의
- 사용자는 비교할 에이전트 아티팩트, 대상 모델 목록, 평가 데이터셋을 지정하여 비교 태스크를 생성한다.

```yaml
comparison_task:
  name: "Q4 Model Upgrade Evaluation"
  artifact_id: "agent-v2.3"
  models:
    - claude-sonnet-4-6
    - claude-opus-4-7
    - gpt-4o
  dataset_id: "eval-set-finance-001"
  metrics:
    - correctness
    - tool_call_accuracy
    - latency_p95
    - cost_per_query
```

#### FR-C2: 자동화된 비교 실행
- 정의된 태스크를 실행하면 각 모델에 대해 동일한 입력을 전송하고 결과를 수집한다.
- 병렬 실행 지원(모델별 API 호출 동시 처리).
- 실행 중 진행 상태(진행률, 예상 완료 시간, 실시간 비용 추산) 표시.

#### FR-C3: 결과 비교 리포트
- 실행 결과를 정량 지표 + 정성 분석으로 제공한다.

| 지표 | 설명 |
|------|------|
| 정확도 (Correctness) | 예상 출력 대비 일치율 |
| 도구 호출 정확도 | 올바른 도구를 올바른 파라미터로 호출한 비율 |
| 레이턴시 P50/P95 | 응답 시간 분포 |
| 비용 효율 | 쿼리당 비용 대비 정확도 |
| 컨텍스트 활용률 | 입력 대비 실제 활용된 컨텍스트 비율 |
| 실패율 | 오류/타임아웃 발생 비율 |

- 결과는 모델별 레이더 차트, 지표별 순위표, 비용-성능 산점도로 시각화된다.

#### FR-C4: 권장 모델 제안
- 비교 결과와 사용자 지정 우선순위(비용 우선 / 성능 우선 / 균형)에 따라 최적 모델을 추천한다.
- 추천 근거를 자연어 요약으로 제공한다.

#### FR-C5: A/B 비교 모드
- 두 모델을 선택하여 개별 응답을 나란히(side-by-side) 비교하는 인터랙티브 뷰.
- 각 응답에 대한 수동 평가(thumbs up/down, 코멘트) 수집 가능.

---

### 4.4 모듈 D — AIOps + AI 에이전트 협업

#### FR-D1: 운영 모니터링
- 프로덕션 에이전트의 실시간 지표를 수집한다:
  - 호출 수, 오류율, 평균 레이턴시, 비용 추산
  - 도구 호출 패턴 분포
  - 컨텍스트 길이 분포

#### FR-D2: 이상 탐지 (Anomaly Detection)
- 지표 임계치 초과 또는 통계적 이상 발생 시 알림을 트리거한다.
- 이상 유형 예시:
  - 오류율 급증 (> 5% 변화)
  - 레이턴시 P95 임계치 초과
  - 비용 예산 초과 예측
  - 특정 도구 호출 실패 급증

#### FR-D3: AI 에이전트 협업 실행
- AIOps 이벤트가 발생하면 AI 에이전트가 다음을 자동 수행한다:
  1. **진단**: 로그 및 지표 분석으로 근본 원인 파악
  2. **영향 평가**: 영향받는 에이전트 아티팩트 및 사용자 목록 식별
  3. **조치 제안**: 롤백, 모델 전환, 파라미터 조정 등 옵션 제안
  4. **승인 후 실행**: 사용자 승인을 받은 후 자동 조치 실행
  5. **결과 보고**: 조치 후 지표 변화 요약 보고

```
[이상 감지] → [AI 에이전트 진단] → [사람 승인] → [자동 조치] → [결과 모니터링]
```

#### FR-D4: 자동화 규칙 엔진
- 사용자는 조건-액션 규칙을 정의할 수 있다.
- 예시:
  ```yaml
  rule:
    name: "auto-fallback-on-error"
    condition: "error_rate > 10% for 5min"
    action: "switch_model to fallback_model"
    requires_approval: false
  ```

#### FR-D5: 운영 리포트
- 일간/주간 운영 요약 리포트 자동 생성:
  - 모델별 사용량 및 비용
  - 상위 오류 유형
  - 성능 트렌드
  - AI 에이전트 자동 조치 이력

---

## 5. 비기능 요구사항 (Non-Functional Requirements)

| 항목 | 요구사항 |
|------|---------|
| **성능** | 비교 분석 태스크(100개 케이스 기준) 10분 이내 완료 |
| **가용성** | 모니터링 모듈 99.9% 업타임 |
| **확장성** | 모델 레지스트리 200개 이상 모델 등록 지원 |
| **보안** | API 키는 암호화 저장, RBAC으로 접근 제어 |
| **감사** | 모든 모델 전환 및 자동 조치 이력 보존 (최소 1년) |
| **연동** | REST API 및 SDK 제공 (Python, TypeScript) |

---

## 6. 시스템 아키텍처 (System Architecture)

```
┌─────────────────────────────────────────────────────────────┐
│                        Web UI / CLI                          │
└────────────────────────┬────────────────────────────────────┘
                         │ REST API / WebSocket
┌────────────────────────▼────────────────────────────────────┐
│                     API Gateway                              │
└──┬──────────┬──────────┬──────────────┬─────────────────────┘
   │          │          │              │
┌──▼──┐  ┌───▼───┐  ┌───▼────┐  ┌──────▼──────┐
│  A  │  │   B   │  │   C    │  │     D        │
│Agent│  │Model  │  │Compare │  │  AIOps       │
│Mgmt │  │Registry│ │Engine  │  │  + AI Agent  │
└──┬──┘  └───┬───┘  └───┬────┘  └──────┬──────┘
   │          │          │              │
┌──▼──────────▼──────────▼──────────────▼──────┐
│              Core Data Layer                   │
│  PostgreSQL (메타데이터) + S3 (아티팩트/결과)  │
│  TimeSeries DB (운영 지표)                     │
└───────────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│              LLM Adapter Layer                               │
│  Anthropic │ OpenAI │ Google │ Custom (OpenAI-compat)        │
└─────────────────────────────────────────────────────────────┘
```

### 6.1 핵심 서비스 구성

| 서비스 | 역할 |
|--------|------|
| `artifact-service` | 에이전트 아티팩트 CRUD, 버전 관리, 의존성 분석 |
| `model-registry-service` | 모델 메타데이터 관리, 호환성 매핑 |
| `comparison-engine` | 비교 태스크 스케줄링, 병렬 실행, 결과 집계 |
| `aiops-service` | 지표 수집, 이상 탐지, 규칙 엔진 |
| `ai-agent-runner` | AIOps 이벤트 처리 AI 에이전트 실행 환경 |
| `llm-adapter` | 각 LLM 공급자 API 추상화 레이어 |

---

## 7. 데이터 모델 (Data Model)

### 7.1 핵심 엔티티

```
Agent
  id, name, description, owner, created_at, updated_at

AgentArtifact
  id, agent_id, type(prompt|mcp|skill|tool_schema), 
  content, version, model_requirements[], created_at

ModelRegistry
  id, name, provider, family, version, capabilities{},
  characteristics{}, pricing{}, api_config{},
  status(active|deprecated|retired), deprecated_at

ModelVariant
  id, artifact_id, model_id, content, notes, created_at

ComparisonTask
  id, name, artifact_id, model_ids[], dataset_id,
  metrics[], status, created_at, completed_at

ComparisonResult
  id, task_id, model_id, metrics{}, raw_outputs[],
  cost_usd, created_at

OpsMetric
  timestamp, agent_id, model_id, metric_name, value

AIOpsEvent
  id, agent_id, model_id, event_type, severity,
  description, status, actions[], created_at
```

---

## 8. 사용자 시나리오 (User Stories)

### 시나리오 1: 모델 업그레이드 사전 검증
> "기존 에이전트를 claude-sonnet-4-6에서 claude-opus-4-7로 업그레이드하려 한다."

1. 개발자가 에이전트 아티팩트(프롬프트, MCP, Skills)를 시스템에 등록
2. "모델 전환 영향 분석" 실행 → 호환되지 않는 구성 요소 목록 확인
3. 비교 태스크 생성하여 두 모델에 대한 벤치마크 실행
4. 결과 리포트에서 성능 차이 및 비용 변화 확인
5. 최적 모델 선택 후 모델별 프롬프트 변형 등록

### 시나리오 2: 프로덕션 이상 자동 대응
> "프로덕션에서 도구 호출 실패율이 급증했다."

1. AIOps 모니터링이 도구 호출 실패율 8% 이상을 감지
2. AI 에이전트가 로그 분석 → "신규 모델 배포 이후 특정 MCP 도구 스키마 불일치" 진단
3. AI 에이전트가 롤백 또는 MCP 스키마 수정 두 가지 옵션 제안
4. 담당자가 MCP 스키마 수정 선택 및 승인
5. AI 에이전트가 수정 적용 → 5분 후 실패율 정상화 확인

### 시나리오 3: 신규 모델 평가
> "시장에 새로운 LLM이 출시되었다. 기존 에이전트에 적합한지 평가하고 싶다."

1. 신규 모델을 레지스트리에 등록 (capabilities, pricing 입력)
2. 기존 평가 데이터셋으로 비교 태스크 실행
3. 기존 모델 대비 성능·비용 비교 리포트 확인
4. 도입 여부 의사결정

---

## 9. 구현 로드맵 (Roadmap)

### Phase 1 — 기반 구축 (MVP) · 6주

| 주차 | 내용 |
|------|------|
| 1–2 | 데이터 모델 설계, API 기본 구조, LLM 어댑터 레이어 |
| 3–4 | 모듈 A: 에이전트 아티팩트 등록 및 기본 의존성 분석 |
| 5–6 | 모듈 B: 모델 레지스트리 CRUD 및 비교 매트릭스 |

**완료 기준**: 아티팩트 등록, 모델 등록, 기본 호환성 분석 동작

### Phase 2 — 비교 분석 엔진 · 6주

| 주차 | 내용 |
|------|------|
| 7–8 | 비교 태스크 스케줄링 및 병렬 실행 |
| 9–10 | 결과 수집, 지표 계산, 리포트 생성 |
| 11–12 | 시각화, A/B 비교 뷰, 권장 모델 제안 로직 |

**완료 기준**: 3개 이상 모델 동시 비교, 리포트 자동 생성

### Phase 3 — AIOps + AI 에이전트 협업 · 8주

| 주차 | 내용 |
|------|------|
| 13–14 | 운영 지표 수집 파이프라인, 대시보드 |
| 15–16 | 이상 탐지 알고리즘, 알림 시스템 |
| 17–18 | AI 에이전트 진단·조치 워크플로우 |
| 19–20 | 규칙 엔진, 승인 플로우, 운영 리포트 |

**완료 기준**: 이상 감지 → AI 진단 → 승인 → 자동 조치 전 과정 동작

---

## 10. 성공 지표 (Success Metrics)

| 지표 | 목표 |
|------|------|
| 모델 전환 소요 시간 | 수동 대비 60% 단축 |
| 비교 분석 정확도 | 수동 평가와 85% 이상 일치 |
| 이상 감지 MTTD (Mean Time to Detect) | 5분 이내 |
| AIOps 자동 조치 성공률 | 승인된 조치의 90% 이상 성공 |
| 개발자 만족도 | NPS 40 이상 |

---

## 11. 오픈 이슈 및 리스크

| 이슈 | 영향 | 대응 방안 |
|------|------|-----------|
| LLM API 변경 빈도 | 어댑터 레이어 유지보수 부담 | Provider별 어댑터 독립 버전관리 |
| 평가 데이터셋 품질 | 비교 결과 신뢰도 저하 | 데이터셋 검증 프로세스 필수화 |
| 비교 실행 비용 | API 호출 비용 급증 | 샘플링 전략 및 비용 캡 설정 |
| AI 에이전트 오판단 | 잘못된 자동 조치 | 고위험 조치 인간 승인 필수화 |
| 프라이버시 | 프롬프트에 민감 정보 포함 가능 | 데이터 마스킹, 온프레미스 옵션 |

---

## 12. 용어 정의 (Glossary)

| 용어 | 정의 |
|------|------|
| **LLM-Aware** | 특정 LLM 모델의 특성을 인지하고 이에 최적화된 설계 방식 |
| **Agent Artifact** | 에이전트를 구성하는 프롬프트, MCP 설정, Skills의 총칭 |
| **Model Variant** | 동일 기능의 아티팩트를 특정 모델에 맞게 최적화한 버전 |
| **Impact Analysis** | 모델 전환 시 영향받는 아티팩트와 수정 필요 사항 분석 |
| **Comparison Task** | 여러 모델에 대한 동일 평가를 수행하는 작업 단위 |
| **AIOps** | AI를 활용하여 운영 이슈를 자동 탐지·진단·해결하는 방법론 |
| **MCP** | Model Context Protocol, 에이전트 도구 정의 및 서버 통신 규약 |
