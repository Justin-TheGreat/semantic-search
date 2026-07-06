import pytest
from pydantic import ValidationError


def test_all_routes_registered():
    from src.main import app

    paths = {r.path for r in app.routes}
    assert {"/health", "/ready", "/search", "/chat", "/metrics"} <= paths


def test_chat_request_guardrail_rejects_oversized_query():
    from src.models import ChatRequest

    with pytest.raises(ValidationError):
        ChatRequest(query="x" * 501)
    assert ChatRequest(query="ok").query == "ok"


def test_config_has_capstone_fields():
    from src.config import settings

    assert settings.vllm_base_url.endswith("/v1")
    assert settings.vllm_model
    assert settings.reranker_model
    assert isinstance(settings.enable_hybrid, bool)
    assert 0 < settings.semantic_cache_threshold <= 1
