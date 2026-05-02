# Agent Management Guide

이 문서는 LLM Management System의 **모듈 A (에이전트 관리)** 기능을 상세히 설명합니다. 에이전트의 구성 요소인 아티팩트를 등록하고, 모델별 최적화 버전을 관리하는 방법을 다룹니다.

---

## 1. 에이전트 및 아티팩트 개념

### 1.1 에이전트 (Agent)
시스템에서 관리하는 논리적인 서비스 단위입니다. 하나의 에이전트는 여러 종류의 아티팩트를 가질 수 있습니다.

### 1.2 아티팩트 (Agent Artifact)
에이전트를 구성하는 구체적인 설정 및 코드 자산입니다.
- **Prompt**: 시스템/사용자 프롬프트 템플릿
- **MCP (Model Context Protocol)**: 도구 정의 및 서버 설정
- **Skill**: 에이전트가 실행 가능한 독립적인 기능 모듈
- **Tool Schema**: 함수 호출을 위한 JSON 스키마 및 파라미터 설명

---

## 2. 주요 기능 워크플로우

### 2.1 아티팩트 등록 및 의존성 분석 (FR-A1, FR-A2)
사용자가 아티팩트를 등록하면 시스템은 자동으로 해당 아티팩트가 요구하는 **모델 특화 기능(Model Dependency)**을 감지합니다.

- **감지 항목**:
  - `tool_choice: "required"` (도구 호출 강제 여부)
  - `vision` (이미지 입력 지원 여부)
  - `parallel_tool_calls` (병렬 도구 호출 지원)
  - `extended_thinking` (추론 모델 지원)

### 2.2 모델 전환 영향 분석 (Impact Analysis, FR-A3)
특정 에이전트를 현재 모델(예: Claude 3.5)에서 대상 모델(예: Claude 4)로 전환할 때의 호환성을 미리 진단합니다.

- **진단 결과**:
  - **Compatible**: 모든 기능이 대상 모델에서 지원됨
  - **Partial**: 일부 비필수 기능이 미지원되나 동작 가능
  - **Incompatible**: 필수 기능(예: 필수 도구 호출)이 미지원되어 정상 동작 불가

### 2.3 모델별 변형 관리 (Model Variant, FR-A4)
동일한 프롬프트나 스키마라도 모델마다 최적의 성능을 내는 형태가 다를 수 있습니다. 시스템은 하나의 아티팩트에 대해 모델별 **변형(Variant)**을 생성하고 관리할 수 있게 지원합니다.

---

## 3. API 사용 예시

### 에이전트 등록
```bash
curl -X POST http://localhost:47000/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Customer Support Bot",
    "description": "고객 응대 및 도구 호출 전용 에이전트",
    "owner": "support-team"
  }'
```

### 아티팩트(MCP) 등록
```bash
curl -X POST http://localhost:47000/agents/{agent_id}/artifacts \
  -H "Content-Type: application/json" \
  -d '{
    "type": "mcp",
    "content": {
      "tool_choice": "required",
      "tools": [
        {"name": "get_user_info", "description": "사용자 정보를 조회합니다"}
      ]
    }
  }'
```

### 모델 전환 영향 분석 실행
```bash
curl "http://localhost:47000/artifacts/{artifact_id}/impact?source_model_id=claude-3-5-sonnet&target_model_id=claude-4-sonnet"
```

---

## 4. 데이터 모델 (Agent Layer)

| 테이블명 | 역할 | 주요 관계 |
|----------|------|-----------|
| `agents` | 에이전트 기본 정보 | `artifacts`와 1:N 관계 |
| `agent_artifacts` | 프롬프트, MCP 등 구성 요소 | `variants`와 1:N 관계 |
| `model_variants` | 특정 모델에 최적화된 아티팩트 내용 | `model_registry`와 N:1 관계 |

---

## 5. 관리자 팁
- **버전 관리**: 아티팩트를 수정할 때마다 자동으로 버전이 업데이트되며, 이전 버전은 S3(MinIO)에 스냅샷으로 보관됩니다.
- **의존성 체크**: 새로운 모델을 도입하기 전, 반드시 영향 분석 API를 통해 아티팩트의 호환성을 먼저 확인하십시오.
- **변형 활용**: 성능 차이가 큰 모델 간 이동 시(예: GPT-4o → Llama 3), 공통 아티팩트보다는 모델별 Variant를 생성하여 최적화된 프롬프트를 적용하는 것을 권장합니다.
---

## 6. 외부 프로젝트 연동 가이드 (Python)

독립적으로 동작하는 에이전트 프로젝트(예: Trading Bot, 분석 스크립트 등)를 본 시스템에 연동하여 실시간 지표를 수집하고 AI 진단을 받는 방법입니다.

### 6.1 연동용 어댑터 클래스 (`mgmt_adapter.py`)

에이전트 프로젝트 내부에 아래 클래스를 추가하여 LLM 호출 시마다 지표를 보고합니다.

```python
import requests
import time
from datetime import datetime
from typing import Optional

class LLMManagementAdapter:
    def __init__(self, agent_id: str, base_url: str = "http://localhost:47000"):
        self.agent_id = agent_id
        self.base_url = base_url

    def report_call(self, model_id: str, input_tokens: int, output_tokens: int, 
                    latency_ms: float, success: bool = True, error_msg: Optional[str] = None):
        """지표 및 이벤트를 시스템에 보고합니다."""
        # 1. 지표(Metrics) 전송
        metrics = [
            {"name": "latency", "val": latency_ms},
            {"name": "input_tokens", "val": float(input_tokens)},
            {"name": "output_tokens", "val": float(output_tokens)},
            {"name": "success_rate", "val": 1.0 if success else 0.0}
        ]
        for m in metrics:
            payload = {
                "agent_id": self.agent_id,
                "model_id": model_id,
                "metric_name": m["name"],
                "value": m["val"]
            }
            try:
                requests.post(f"{self.base_url}/metrics", json=payload, timeout=1)
            except: pass

        # 2. 장애 이벤트(Event) 전송 (실패 시)
        if not success and error_msg:
            event = {
                "agent_id": self.agent_id,
                "model_id": model_id,
                "event_type": "llm_failure",
                "severity": "high",
                "description": error_msg
            }
            try:
                requests.post(f"{self.base_url}/events", json=event, timeout=1)
            except: pass
```

### 6.2 적용 예시

```python
mgmt = LLMManagementAdapter(agent_id="YOUR_AGENT_UUID")

start = time.time()
try:
    # LLM 호출 실행
    response = client.messages.create(model="claude-4-sonnet", ...)
    
    # 성공 지표 보고
    mgmt.report_call(
        model_id="claude-4-sonnet",
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        latency_ms=(time.time() - start) * 1000
    )
except Exception as e:
    # 실패 이벤트 보고
    mgmt.report_call(model_id="claude-4-sonnet", ..., success=False, error_msg=str(e))
```
