"""Detect model-specific feature dependencies in agent artifacts (FR-A2)."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CompatibilityLevel(str, Enum):
    COMPATIBLE = "compatible"
    PARTIAL = "partial"
    INCOMPATIBLE = "incompatible"


@dataclass
class ModelDependency:
    feature: str
    required: bool
    description: str

    def to_dict(self) -> dict:
        return {
            "feature": self.feature,
            "required": self.required,
            "description": self.description,
        }


class ArtifactDependencyAnalyzer:
    """
    Scans artifact content and returns a list of ModelDependency objects
    describing which model capabilities the artifact relies on.
    """

    def analyze(self, artifact_type: str, content: dict) -> list[ModelDependency]:
        handlers = {
            "mcp": self._analyze_mcp,
            "tool_schema": self._analyze_tool_schema,
            "prompt": self._analyze_prompt,
            "skill": self._analyze_skill,
        }
        handler = handlers.get(artifact_type)
        return handler(content) if handler else []

    # ── Per-type analysis ─────────────────────────────────────────────────────

    def _analyze_mcp(self, content: dict) -> list[ModelDependency]:
        deps: list[ModelDependency] = []

        if content.get("tool_choice") == "required":
            deps.append(ModelDependency(
                feature="tool_choice_required",
                required=True,
                description="tool_choice='required' — 모델이 반드시 도구를 호출해야 함",
            ))

        if content.get("parallel_tool_calls") is True:
            deps.append(ModelDependency(
                feature="parallel_tool_calls",
                required=False,
                description="병렬 도구 호출 사용 — 미지원 모델은 순차 실행으로 폴백",
            ))

        if content.get("tools"):
            deps.append(ModelDependency(
                feature="tool_use",
                required=True,
                description="도구 정의 포함 — tool_use 지원 모델 필요",
            ))

        return deps

    def _analyze_tool_schema(self, content: dict) -> list[ModelDependency]:
        deps: list[ModelDependency] = [
            ModelDependency(
                feature="tool_use",
                required=True,
                description="도구 스키마 아티팩트 — tool_use 지원 모델 필요",
            )
        ]
        # Detect nested object parameters that exceed simple models' parsing
        params = content.get("input_schema", {}).get("properties", {})
        for _, v in params.items():
            if v.get("type") == "object" and v.get("properties"):
                deps.append(ModelDependency(
                    feature="structured_output",
                    required=False,
                    description="중첩 객체 파라미터 포함 — structured_output 권장",
                ))
                break
        return deps

    def _analyze_prompt(self, content: dict) -> list[ModelDependency]:
        deps: list[ModelDependency] = []
        text = str(content.get("text", "") or content.get("content", ""))

        # Vision hint: base64 image or image URL
        if "data:image/" in text or "<image>" in text:
            deps.append(ModelDependency(
                feature="vision",
                required=True,
                description="프롬프트에 이미지 데이터 포함 — vision 지원 모델 필요",
            ))

        # Long context hint: estimated token count via rough char/4 heuristic
        estimated_tokens = len(text) // 4
        if estimated_tokens > 100_000:
            deps.append(ModelDependency(
                feature="long_context",
                required=True,
                description=f"프롬프트 토큰 추정 {estimated_tokens:,} — 대형 컨텍스트 윈도우 필요",
            ))

        return deps

    def _analyze_skill(self, content: dict) -> list[ModelDependency]:
        deps: list[ModelDependency] = []
        if content.get("requires_tool_use"):
            deps.append(ModelDependency(
                feature="tool_use",
                required=True,
                description="Skill이 tool_use를 명시적으로 요구함",
            ))
        return deps

    # ── Compatibility check ───────────────────────────────────────────────────

    def check_compatibility(
        self,
        dependencies: list[ModelDependency],
        model_capabilities: dict,
    ) -> CompatibilityLevel:
        """
        Compare artifact dependencies against a model's capabilities dict.
        Returns INCOMPATIBLE if any required feature is missing,
                PARTIAL if any optional feature is missing,
                COMPATIBLE otherwise.
        """
        # Map dependency feature names to capability keys
        feature_map = {
            "tool_use": "tool_use",
            "tool_choice_required": "tool_use",
            "parallel_tool_calls": "parallel_tool_calls",
            "vision": "vision",
            "structured_output": "structured_output",
            "long_context": None,   # checked separately via context_window
        }

        incompatible: list[ModelDependency] = []
        partial: list[ModelDependency] = []

        for dep in dependencies:
            cap_key = feature_map.get(dep.feature)

            if dep.feature == "long_context":
                ctx = model_capabilities.get("context_window", 0)
                if ctx < 100_000:
                    (incompatible if dep.required else partial).append(dep)
                continue

            if cap_key and not model_capabilities.get(cap_key, False):
                (incompatible if dep.required else partial).append(dep)

        if incompatible:
            return CompatibilityLevel.INCOMPATIBLE
        if partial:
            return CompatibilityLevel.PARTIAL
        return CompatibilityLevel.COMPATIBLE
