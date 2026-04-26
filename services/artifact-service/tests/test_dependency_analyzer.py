"""Unit tests for ArtifactDependencyAnalyzer — no DB or external calls needed."""
import pytest
from artifact_service.analyzers.dependency_analyzer import (
    ArtifactDependencyAnalyzer,
    CompatibilityLevel,
    ModelDependency,
)

analyzer = ArtifactDependencyAnalyzer()


class TestMcpAnalysis:
    def test_tool_choice_required_detected(self):
        content = {"tool_choice": "required", "tools": [{"name": "search"}]}
        deps = analyzer.analyze("mcp", content)
        assert any(d.feature == "tool_choice_required" for d in deps)

    def test_parallel_tool_calls_detected(self):
        content = {"parallel_tool_calls": True, "tools": []}
        deps = analyzer.analyze("mcp", content)
        assert any(d.feature == "parallel_tool_calls" for d in deps)

    def test_tool_use_detected_when_tools_present(self):
        content = {"tools": [{"name": "calc"}]}
        deps = analyzer.analyze("mcp", content)
        assert any(d.feature == "tool_use" for d in deps)

    def test_empty_mcp_no_deps(self):
        deps = analyzer.analyze("mcp", {})
        assert deps == []


class TestPromptAnalysis:
    def test_vision_detected_from_base64(self):
        content = {"text": "Look at this: data:image/png;base64,abc..."}
        deps = analyzer.analyze("prompt", content)
        assert any(d.feature == "vision" for d in deps)

    def test_long_context_detected(self):
        long_text = "a" * 400_001  # > 100k tokens (400k chars / 4)
        deps = analyzer.analyze("prompt", {"text": long_text})
        assert any(d.feature == "long_context" for d in deps)

    def test_short_prompt_no_deps(self):
        deps = analyzer.analyze("prompt", {"text": "Hello world"})
        assert deps == []


class TestCompatibilityCheck:
    def test_compatible_when_all_features_present(self):
        deps = [ModelDependency("tool_use", required=True, description="")]
        caps = {"tool_use": True}
        assert analyzer.check_compatibility(deps, caps) == CompatibilityLevel.COMPATIBLE

    def test_incompatible_when_required_feature_missing(self):
        deps = [ModelDependency("vision", required=True, description="")]
        caps = {"vision": False}
        assert analyzer.check_compatibility(deps, caps) == CompatibilityLevel.INCOMPATIBLE

    def test_partial_when_optional_feature_missing(self):
        deps = [ModelDependency("parallel_tool_calls", required=False, description="")]
        caps = {"parallel_tool_calls": False}
        assert analyzer.check_compatibility(deps, caps) == CompatibilityLevel.PARTIAL

    def test_incompatible_takes_priority_over_partial(self):
        deps = [
            ModelDependency("vision", required=True, description=""),
            ModelDependency("parallel_tool_calls", required=False, description=""),
        ]
        caps = {"vision": False, "parallel_tool_calls": False}
        assert analyzer.check_compatibility(deps, caps) == CompatibilityLevel.INCOMPATIBLE
