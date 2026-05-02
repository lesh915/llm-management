"""Pydantic schemas shared across services."""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


# ── Model Registry Schemas ────────────────────────────────────────────────────

class ModelCapabilities(BaseModel):
    context_window: int = Field(..., gt=0, description="최대 입력 토큰 수")
    max_output_tokens: int = Field(..., gt=0)
    vision: bool = False
    tool_use: bool = False
    structured_output: bool = False
    streaming: bool = True
    parallel_tool_calls: bool = False
    extended_thinking: bool = False


class ModelCharacteristics(BaseModel):
    reasoning_depth: Literal["low", "medium", "high"] = "medium"
    instruction_following: Literal["low", "medium", "high"] = "medium"
    code_generation: Literal["low", "medium", "high"] = "medium"
    latency_tier: Literal["low", "medium", "high"] = "medium"


class ModelPricing(BaseModel):
    input_per_1m_tokens: float = Field(..., ge=0.0, description="USD per 1M input tokens")
    output_per_1m_tokens: float = Field(..., ge=0.0, description="USD per 1M output tokens")


class ModelApiConfig(BaseModel):
    endpoint: str
    auth_type: Literal["api_key", "oauth", "none", "custom"] = "api_key"
    sdk: list[str] = []
    # 로컬 모델 전용
    model_name: str | None = None        # 어댑터에 전달할 실제 모델 이름
    openai_compat: bool = False          # OpenAI-compatible API 여부
    api_key: str | None = None           # 암호화된 API 키 (저장용)


class ModelCreate(BaseModel):
    id: str = Field(..., example="claude-sonnet-4-6")
    provider: str
    family: str | None = None
    version: str | None = None
    capabilities: ModelCapabilities
    characteristics: ModelCharacteristics
    pricing: ModelPricing
    api: ModelApiConfig
    is_custom: bool = False


class ModelRead(ModelCreate):
    status: str = "active"
    deprecated_at: str | None = None
    created_at: str | None = None


# ── Artifact Schemas ──────────────────────────────────────────────────────────

class CompatibilityLevel(str, Enum):
    COMPATIBLE = "compatible"
    PARTIAL = "partial"
    INCOMPATIBLE = "incompatible"


class ModelDependency(BaseModel):
    feature: str
    required: bool
    description: str


class ArtifactCreate(BaseModel):
    type: Literal["prompt", "mcp", "skill", "tool_schema"]
    content: dict


class ArtifactRead(ArtifactCreate):
    id: str
    agent_id: str
    version: int
    model_requirements: list[dict] = []
    created_at: str | None = None


# ── Comparison Schemas ────────────────────────────────────────────────────────

class ComparisonTaskCreate(BaseModel):
    name: str
    artifact_id: str | None = None
    baseline_model_id: str | None = None
    models: list[str] = Field(..., min_length=2, description="비교할 모델 ID 목록 (최소 2개)")
    dataset_id: str
    metrics: list[str] = Field(
        default=["correctness", "tool_call_accuracy", "latency_p95", "cost_per_query"]
    )
    max_concurrent_local: int = Field(
        default=2, ge=1, le=10,
        description="로컬 모델 동시 요청 수 제한"
    )


class AgentTurnRead(BaseModel):
    turn_index: int
    thought: str | None = None
    action: dict | None = None
    observation: str | None = None
    response: str | None = None
    state_snapshot: dict | None = None
    metrics: dict | None = None


class AgentSessionRead(BaseModel):
    id: str
    case_id: str
    turns: list[AgentTurnRead] = []


# ── Common Response Wrappers ──────────────────────────────────────────────────

class ApiResponse(BaseModel):
    data: dict | list | None = None
    meta: dict | None = None


class ApiError(BaseModel):
    code: str
    message: str
    details: dict | None = None
