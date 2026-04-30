"""어댑터 팩토리 단위 테스트."""
from __future__ import annotations

import pytest
from unittest.mock import patch

from llm_adapter.factory import get_adapter, decrypt_api_key
from llm_adapter.anthropic_adapter import AnthropicAdapter
from llm_adapter.openai_compat_adapter import OpenAICompatAdapter
from llm_adapter.ollama_adapter import OllamaAdapter


# ── decrypt_api_key ────────────────────────────────────────────────────────────

class TestDecryptApiKey:
    def test_none_returns_local(self):
        assert decrypt_api_key(None) == "local"

    def test_empty_returns_local(self):
        assert decrypt_api_key("") == "local"

    def test_plaintext_fallback(self):
        """암호화되지 않은 값은 그대로 반환 (개발환경)."""
        assert decrypt_api_key("sk-ant-plain-key") == "sk-ant-plain-key"

    def test_encrypted_value_with_valid_key(self):
        """유효한 Fernet 키로 암호화된 값을 복호화."""
        from cryptography.fernet import Fernet
        key = Fernet.generate_key().decode()
        fernet = Fernet(key.encode())
        encrypted = fernet.encrypt(b"sk-secret-key").decode()

        with patch("llm_adapter.factory._fernet", fernet):
            result = decrypt_api_key(encrypted)

        assert result == "sk-secret-key"


# ── get_adapter ────────────────────────────────────────────────────────────────

class TestGetAdapter:
    def _model(self, provider, model_id="test-model", **extra):
        return {
            "id": model_id,
            "provider": provider,
            "is_custom": False,
            "api_config": {"model_name": model_id, **extra},
        }

    def test_anthropic_returns_anthropic_adapter(self):
        record = self._model("Anthropic", model_id="claude-opus-4-7", api_key=None)
        adapter = get_adapter(record)
        assert isinstance(adapter, AnthropicAdapter)

    def test_openai_returns_openai_compat_adapter(self):
        record = self._model("OpenAI", model_id="gpt-4o", api_key=None)
        adapter = get_adapter(record)
        assert isinstance(adapter, OpenAICompatAdapter)
        assert adapter.is_local is False

    def test_google_returns_openai_compat_adapter(self):
        record = self._model("Google", model_id="gemini-1.5-pro", api_key=None)
        adapter = get_adapter(record)
        assert isinstance(adapter, OpenAICompatAdapter)

    def test_ollama_returns_ollama_adapter(self):
        record = self._model("Ollama", model_id="ollama/llama3.2:3b",
                              endpoint="http://ollama:11434")
        adapter = get_adapter(record)
        assert isinstance(adapter, OllamaAdapter)

    def test_vllm_returns_openai_compat_local(self):
        record = self._model("vLLM", model_id="mistral-7b",
                              endpoint="http://vllm:8000/v1")
        adapter = get_adapter(record)
        assert isinstance(adapter, OpenAICompatAdapter)
        assert adapter.is_local is True

    def test_lm_studio_returns_openai_compat_local(self):
        record = self._model("LM Studio", model_id="phi-3",
                              endpoint="http://localhost:1234/v1")
        adapter = get_adapter(record)
        assert isinstance(adapter, OpenAICompatAdapter)
        assert adapter.is_local is True

    def test_localai_returns_openai_compat_local(self):
        record = self._model("LocalAI", model_id="gguf-model",
                              endpoint="http://localhost:8080/v1")
        adapter = get_adapter(record)
        assert isinstance(adapter, OpenAICompatAdapter)
        assert adapter.is_local is True

    def test_custom_openai_compat(self):
        record = {
            "id": "custom-model",
            "provider": "CustomProvider",
            "is_custom": True,
            "api_config": {
                "model_name": "custom-model",
                "endpoint": "http://my-server/v1",
                "openai_compat": True,
            },
        }
        adapter = get_adapter(record)
        assert isinstance(adapter, OpenAICompatAdapter)

    def test_unknown_provider_raises(self):
        record = {
            "id": "unknown-model",
            "provider": "UnknownProvider",
            "is_custom": False,
            "api_config": {},
        }
        with pytest.raises(ValueError, match="Unsupported provider"):
            get_adapter(record)

    def test_model_name_fallback_to_id(self):
        """api_config에 model_name 없으면 id를 사용."""
        record = {
            "id": "claude-opus-4-7",
            "provider": "Anthropic",
            "is_custom": False,
            "api_config": {},   # no model_name key
        }
        adapter = get_adapter(record)
        assert isinstance(adapter, AnthropicAdapter)
        assert adapter.model_id == "claude-opus-4-7"
