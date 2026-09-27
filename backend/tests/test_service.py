import pytest
from sqlalchemy.dialects import postgresql

from backend.app.generation.grounding import build_context, build_prompt
from backend.app.ingestion.chunking import token_count
from backend.app.retrieval.retriever import authorized_statement


def test_grounded_multi_document_answer_and_telemetry(service):
    result = service.ask("What is the treasury Level-2 threshold and who must be notified?", "treasury")
    assert not result["abstained"]
    assert "10,000,000" in result["answer"]
    assert "Compliance Duty Officer" in result["answer"]
    supplied = {chunk["chunk_id"]: chunk for chunk in result["retrieval_context"]}
    assert result["citations"]
    for citation in result["citations"]:
        assert citation["excerpt"] in supplied[citation["chunk_id"]]["text"]
        assert f"[{citation['citation_id']}]" in result["answer"]
    assert result["token_usage"]["total_tokens"] > 0
    assert result["latency_ms"] > 0
    assert all(stage in result["timings"] for stage in ["retrieval_ms", "generation_ms", "citation_verification_ms"])


@pytest.mark.parametrize("question", [
    "What is the orbital period of Jupiter?",
    "What is the CEO personal mobile telephone number?",
    "What is tomorrow's EUR USD exchange rate?",
])
def test_out_of_corpus_abstention(service, question):
    result = service.ask(question, "analyst")
    assert result["abstained"]
    assert not result["citations"]


def test_review_morphology(service):
    result = service.ask("What is the privileged access review interval?", "analyst")
    assert not result["abstained"]
    assert "90 calendar days" in result["answer"]


def test_context_budget_skips_whole_chunks(service):
    contexts = service.ask("What is the treasury risk threshold?", "treasury")["retrieval_context"]
    result = build_context(contexts, 160)
    assert sum(token_count(row["text"]) + token_count(row["document_title"]) + 35 for row in result) <= 160


def test_prompt_has_trust_boundary(service):
    contexts = service.ask("What is the treasury risk threshold?", "treasury")["retrieval_context"]
    messages = build_prompt("treasury threshold", contexts)
    assert messages[0]["role"] == "system"
    assert "untrusted_evidence" in messages[1]["content"]
    assert all(row["text"] not in messages[0]["content"] for row in contexts)


def test_profile_mismatch_requires_reingest(service):
    service.settings.embedding_model = "changed-profile"
    result = service.ask("What is the treasury risk threshold?", "treasury")
    assert result["abstained"]
    assert "pipeline_error_fail_closed:ValueError" in result["guardrail_decisions"]


def test_sql_permission_predicate():
    sql = str(authorized_statement("analyst").compile(dialect=postgresql.dialect()))
    assert "EXISTS" in sql and "chunk_roles.role" in sql
    assert "chunks.active IS true" in sql and "chunks.quarantined IS false" in sql
    assert "EXISTS" not in str(authorized_statement("admin"))
    with pytest.raises(PermissionError):
        authorized_statement("superuser")


def test_local_completion_budget(service):
    service.settings.max_completion_tokens = 64
    result = service.ask("What is the treasury risk threshold approval and notification process?", "treasury")
    assert sum(token_count(citation["excerpt"]) for citation in result["citations"]) <= 64
