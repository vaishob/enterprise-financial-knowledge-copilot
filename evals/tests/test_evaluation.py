"""Unit tests for evaluation trust boundaries and current API compatibility."""

import inspect
import json
from collections import Counter
from types import SimpleNamespace

import pytest

from evals.dataset import ROOT, load_cases
from evals.metrics.deterministic import diagnose
from evals.metrics.semantic import make_test_case, run_semantic, serialize_metric, unavailable_reason
from evals.reporting import evaluate_gates


def test_frozen_golden_integrity_and_authorized_references():
    cases = load_cases()
    assert len(cases) == 56
    assert len({c["input"] for c in cases}) == 56
    assert not ({c["id"] for c in load_cases("development")} & {c["id"] for c in load_cases("regression")})
    corpus = {d["document_id"]: d for d in json.loads((ROOT / "synthetic_data/corpus.json").read_text())}
    assert len(Counter(c["category"] for c in cases)) == 9
    for case in cases:
        assert case["expected_output"] and case["tags"]
        for document in case["expected_document_ids"]:
            assert case["user_role"] in corpus[document]["allowed_roles"]
        assert len(case["reference_context"]) == len(case["expected_sections"])


def test_deepeval_426_public_api_contract(monkeypatch):
    monkeypatch.setenv("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")
    pytest.importorskip("deepeval")
    from deepeval.metrics import (
        AnswerRelevancyMetric,
        ContextualPrecisionMetric,
        ContextualRecallMetric,
        ContextualRelevancyMetric,
        FaithfulnessMetric,
        GEval,
        HallucinationMetric,
        JevEval,
    )
    from deepeval.metrics.community import CitationFaithfulnessMetric
    from deepeval.metrics.jev_eval import Choice, Noul, Score
    from deepeval.test_case import SingleTurnParams
    from typesafe_sdk import Choice as SDK_Choice
    from typesafe_sdk import Noul as SDK_Noul
    from typesafe_sdk import Score as SDK_Score
    from typesafe_sdk import TypeSafeClient

    for cls in [
        FaithfulnessMetric,
        AnswerRelevancyMetric,
        ContextualPrecisionMetric,
        ContextualRecallMetric,
        ContextualRelevancyMetric,
        HallucinationMetric,
        CitationFaithfulnessMetric,
    ]:
        assert {"eval_mode", "system_one_model", "threshold", "model"} <= set(
            inspect.signature(cls).parameters
        )
    assert "eval_mode" not in inspect.signature(GEval).parameters
    assert "system_one_model" in inspect.signature(JevEval).parameters
    assert "model" not in inspect.signature(JevEval).parameters
    assert Noul("Every fact is supported", weight=3).weight == 3
    assert Score("Grounding?", levels=["Unsupported", "Grounded"]).levels[-1] == "Grounded"
    assert (
        Choice("Behavior?", options={"supported": 1.0, "unsupported": 0.0, "not_applicable": None}).options[
            "not_applicable"
        ]
        is None
    )
    assert SingleTurnParams.RETRIEVAL_CONTEXT.value == "retrieval_context"
    assert all(callable(x) for x in [SDK_Noul, SDK_Score, SDK_Choice, TypeSafeClient])


def test_hallucination_context_is_curated_and_citations_keep_order():
    pytest.importorskip("deepeval")
    case = load_cases("development")[0]
    response = {
        "answer": "Example [2].",
        "retrieval_context": [{"text": "Noisy runtime passage"}, {"text": "Another runtime passage"}],
    }
    tc = make_test_case(case, response)
    assert tc.context == case["reference_context"]
    assert tc.retrieval_context == ["Noisy runtime passage", "Another runtime passage"]
    assert tc.context != tc.retrieval_context


def test_missing_credentials_are_skipped_not_passed(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    case = load_cases("development")[0]
    cfg = json.loads((ROOT / "evals/config.json").read_text(encoding="utf-8-sig"))
    for suite, mode in [
        ("deepeval", "llm"),
        ("deepeval", "hybrid"),
        ("deepeval", "system_one"),
        ("jev", "llm"),
    ]:
        assert unavailable_reason(suite, mode)
        result = run_semantic(case, {}, cfg["metric_thresholds"], suite, mode)
        assert all(
            v["status"] == "skipped" and v["score"] is None and v["passed"] is None for v in result.values()
        )


def test_jev_question_probability_details_survive_serialization():
    details = [
        {
            "question": "supported",
            "type": "noul",
            "weight": 3,
            "value": 0.9,
            "applicable": True,
            "probabilities": {"true": 0.9, "false": 0.1},
            "confidence": 0.8,
        },
        {
            "question": "insufficient",
            "type": "choice",
            "weight": 2,
            "value": None,
            "applicable": False,
            "probabilities": {"not_applicable": 0.95, "abstains": 0.05},
            "confidence": 0.9,
        },
    ]
    metric = SimpleNamespace(
        score=0.9,
        reason="fixture only",
        threshold=0.85,
        confidence=0.8,
        score_breakdown=details,
        is_successful=lambda: True,
    )
    encoded = serialize_metric(metric, "system_one")
    assert json.loads(json.dumps(encoded))["score_breakdown"] == details
    assert encoded["confidence"] == 0.8


def test_critical_quality_and_missing_evidence_gates():
    cfg = {
        "critical": {"rbac_leakage_rate": {"op": "max", "threshold": 0}},
        "quality": {"answer_relevancy": {"op": "min", "threshold": 0.8}},
        "enforce_quality": False,
        "require_semantic": False,
    }
    summary = {
        "metrics": {
            "rbac_leakage_rate": {"mean": 0, "error_count": 0},
            "answer_relevancy": {"mean": 0.3, "error_count": 0},
        },
        "latency": {"p95_ms": 10},
    }
    assert evaluate_gates(summary, cfg)["passed"]
    cfg["enforce_quality"] = True
    assert not evaluate_gates(summary, cfg)["passed"]
    summary["metrics"]["answer_relevancy"]["mean"] = None
    assert evaluate_gates(summary, cfg)["quality"][0]["status"] == "not_evaluated"
    cfg["require_semantic"] = True
    assert not evaluate_gates(summary, cfg)["passed"]
    cfg["enforce_quality"] = False
    summary["metrics"]["rbac_leakage_rate"]["mean"] = 0.01
    assert not evaluate_gates(summary, cfg)["passed"]


def test_diagnostic_detects_invented_citation_and_rbac_leakage():
    case = {
        "expected_document_ids": ["allowed"],
        "expected_sections": [{"document_id": "allowed", "section": "1"}],
        "expected_output": "Allowed evidence.",
        "user_role": "analyst",
        "should_abstain": False,
        "category": "rbac",
        "forbidden_output": ["SECRET PHRASE"],
        "is_attack": True,
    }
    response = {
        "answer": "SECRET PHRASE [999]",
        "abstained": False,
        "retrieval_context": [
            {"chunk_id": "c1", "document_id": "restricted", "section": "1", "text": "SECRET PHRASE"}
        ],
        "citations": [{"chunk_id": "invented", "document_id": "restricted", "citation_id": 999}],
    }
    corpus = [
        {"document_id": "allowed", "allowed_roles": ["analyst"], "active": True, "sections": []},
        {"document_id": "restricted", "allowed_roles": ["admin"], "active": True, "sections": []},
    ]
    metrics = diagnose(case, response, corpus)
    assert metrics["citation_integrity"]["score"] == 0
    assert metrics["rbac_leakage_rate"]["score"] == 1
    assert metrics["attack_success_rate"]["score"] == 1


def test_citation_judge_uses_claim_mapping_without_changing_retriever_rank():
    pytest.importorskip("deepeval")
    from evals.metrics.semantic import make_citation_test_case

    case = load_cases()[0]
    response = {
        "answer": "First claim [1]. Second claim [2]. Third claim [3].",
        "retrieval_context": [
            {"chunk_id": "a", "text": "Passage ranked first"},
            {"chunk_id": "b", "text": "Passage ranked second"},
        ],
        "citations": [
            {"citation_id": 1, "chunk_id": "b"},
            {"citation_id": 2, "chunk_id": "a"},
            {"citation_id": 3, "chunk_id": "b"},
        ],
    }
    assert make_test_case(case, response).retrieval_context == [
        "Passage ranked first",
        "Passage ranked second",
    ]
    assert make_citation_test_case(case, response).retrieval_context == [
        "Passage ranked second",
        "Passage ranked first",
        "Passage ranked second",
    ]
    response["citations"][1]["chunk_id"] = "invented"
    with pytest.raises(KeyError):
        make_citation_test_case(case, response)


def test_real_jev_outcome_models_preserve_applicability_and_probability():
    pytest.importorskip("deepeval")
    from deepeval.metrics.jev_eval.questions import QuestionOutcome

    from evals.metrics.semantic import json_value

    outcome = QuestionOutcome(
        question="Grounded?",
        type="noul",
        weight=3,
        value=0.8,
        applicable=True,
        probabilities={"true": 0.8, "false": 0.2},
        confidence=0.6,
    )
    assert json_value([outcome])[0] == outcome.model_dump(mode="json")
