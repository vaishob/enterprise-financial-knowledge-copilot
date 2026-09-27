import json
import os

import httpx
import pytest
from pydantic import SecretStr

from backend.app.providers.embeddings import OpenAIEmbedder
from backend.app.providers.generation import OllamaGenerator, OpenAIGenerator


def test_openai_generation_adapter_contract(settings, monkeypatch):
    original_client = httpx.Client
    captured = []

    def handler(request):
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"claims":[],"abstain":true}'}}],
                                        "usage": {"prompt_tokens": 42, "completion_tokens": 8}})
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs))
    settings.llm_api_key = SecretStr("synthetic-provider-test-key")
    output = OpenAIGenerator(settings).generate("Unsupported question?", [])
    assert output.claims.abstain
    assert output.input_tokens == 42 and output.output_tokens == 8 and not output.estimated
    assert captured[0]["messages"][0]["role"] == "system"
    assert captured[0]["response_format"] == {"type": "json_object"}


def test_openai_embedding_adapter_orders_provider_rows(settings, monkeypatch):
    original_client = httpx.Client
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={
        "data": [{"index": 1, "embedding": [0.0, 1.0]}, {"index": 0, "embedding": [1.0, 0.0]}]}))
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: original_client(transport=transport, **kwargs))
    settings.embedding_api_key = SecretStr("synthetic-provider-test-key")
    assert OpenAIEmbedder(settings).embed(["first", "second"]) == [[1.0, 0.0], [0.0, 1.0]]


def test_ollama_adapter_structured_format(settings, monkeypatch):
    original_client = httpx.Client
    captured = []

    def handler(request):
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"message": {"content": '{"claims":[],"abstain":true}'},
                                        "prompt_eval_count": 40, "eval_count": 7})
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs))
    result = OllamaGenerator(settings).generate("Unsupported question?", [])
    assert result.claims.abstain and result.input_tokens == 40
    assert captured[0]["stream"] is False and "properties" in captured[0]["format"]


def test_bedrock_adapter_converse_contract(settings, monkeypatch):
    from backend.app.providers.generation import BedrockGenerator
    calls = []

    class Client:
        def converse(self, **kwargs):
            calls.append(kwargs)
            return {"output": {"message": {"content": [{"text": '{"claims":[],"abstain":true}'}]}},
                    "usage": {"inputTokens": 35, "outputTokens": 6}}
    # No AWS credential discovery or network is needed to validate wire conversion.
    adapter = object.__new__(BedrockGenerator)
    adapter.settings, adapter.client = settings, Client()
    result = adapter.generate("Unsupported question?", [])
    assert result.input_tokens == 35 and result.output_tokens == 6
    assert calls[0]["system"][0]["text"]
    assert calls[0]["messages"][0]["role"] == "user"


@pytest.mark.postgres
@pytest.mark.skipif(not os.environ.get("TEST_POSTGRES_URL"), reason="TEST_POSTGRES_URL absent; live pgvector unavailable")
def test_live_postgres_authorized_vector_retrieval():
    from backend.app.core.config import Settings
    from backend.app.service import RagService
    # Use a dedicated ephemeral database: ingestion replaces only this application's chunks.
    service = RagService(Settings(database_url=os.environ["TEST_POSTGRES_URL"], app_env="test"))
    assert service.db.is_postgres
    assert service.ingest()["chunks"] > 0
    response = service.ask("What is the treasury Level-2 threshold?", "treasury")
    assert not response["abstained"]
    assert all("treasury" in chunk["allowed_roles"] for chunk in response["retrieval_context"])
    limited = service.ask("What is the liquidity stress survival horizon?", "analyst")
    assert all("analyst" in chunk["allowed_roles"] for chunk in limited["retrieval_context"])
