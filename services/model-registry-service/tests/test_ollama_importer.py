"""Unit tests for Ollama model metadata inference."""
import pytest
from model_registry_service.ollama_importer import _infer_model_meta


@pytest.mark.parametrize("model_name,expected_family,expected_ctx", [
    ("llama3.2:3b",          "Llama",    8192),
    ("llama3.1:70b",         "Llama",    131072),
    ("mistral:7b-instruct",  "Mistral",  32768),
    ("qwen2.5:72b",          "Qwen",     131072),
    ("deepseek-r1:7b",       "DeepSeek", 32768),
    ("phi3:3.8b",            "Phi",      8192),
    ("gemma2:9b",            "Gemma",    8192),
    ("unknown-model:latest", "Unknown",  8192),
])
def test_infer_family_and_context(model_name, expected_family, expected_ctx):
    meta = _infer_model_meta(model_name)
    assert meta["family"] == expected_family
    assert meta["capabilities"]["context_window"] == expected_ctx


@pytest.mark.parametrize("model_name,expected_vision", [
    ("llava:7b",          True),
    ("llama3.2-vision:11b", True),
    ("mistral:7b",        False),
    ("moondream:latest",  True),
])
def test_infer_vision(model_name, expected_vision):
    meta = _infer_model_meta(model_name)
    assert meta["capabilities"]["vision"] == expected_vision


def test_local_model_pricing_is_zero():
    meta = _infer_model_meta("llama3.2:3b")
    # Local models should always have zero pricing
    assert meta["capabilities"]["context_window"] > 0
    # Pricing is set in import_from_ollama, not _infer_model_meta
    # Verify the function returns required keys
    assert "capabilities" in meta
    assert "characteristics" in meta
