"""Verified against DeepEval 4.2.6 and typesafe-sdk 0.7.1 on 2026-09-26.

Imports are lazy so the offline core remains usable without judge dependencies.
No credential means skipped; provider errors mean errors, never passing scores.
"""

from __future__ import annotations

import importlib.util
import os

SEMANTIC_NAMES = (
    "faithfulness",
    "answer_relevancy",
    "contextual_precision",
    "contextual_recall",
    "contextual_relevancy",
    "citation_faithfulness",
    "hallucination",
    "financial_answer_quality",
)


def unavailable_reason(suite="deepeval", eval_mode="llm") -> str | None:
    if importlib.util.find_spec("deepeval") is None:
        return "deepeval is not installed; install the eval extra"
    if suite == "jev" or eval_mode in {"hybrid", "system_one"}:
        if importlib.util.find_spec("typesafe_sdk") is None:
            return "typesafe-sdk is not installed"
        if not os.getenv("TYPESAFE_API_KEY"):
            return "TYPESAFE_API_KEY absent; Jev evaluation skipped"
    if suite != "jev" and eval_mode != "system_one" and not os.getenv("OPENAI_API_KEY"):
        return "OPENAI_API_KEY absent; DeepEval LLM judge evaluation skipped"
    return None


def financial_jev(threshold=0.85):
    from deepeval.metrics import JevEval
    from deepeval.metrics.jev_eval import Choice, Noul, Score
    from deepeval.test_case import SingleTurnParams

    return JevEval(
        name="Financial RAG Grounding",
        evaluation_params=[
            SingleTurnParams.INPUT,
            SingleTurnParams.ACTUAL_OUTPUT,
            SingleTurnParams.RETRIEVAL_CONTEXT,
        ],
        questions=[
            Noul(
                "Every material factual claim in actual_output is supported by retrieval_context.", weight=3
            ),
            Noul(
                "Every numerical value, date, threshold and named policy role stated in actual_output is supported by retrieval_context.",
                weight=3,
            ),
            Noul("actual_output avoids presenting unsupported assumptions as facts.", weight=3),
            Choice(
                "When retrieval_context is insufficient for input, how does actual_output respond?",
                options={
                    "explicitly_abstains_or_expresses_uncertainty": 1.0,
                    "silently_omits_missing_answer": 0.4,
                    "invents_an_answer": 0.0,
                    "evidence_is_sufficient": None,
                },
                weight=2,
            ),
            Score(
                "How grounded is actual_output in retrieval_context?",
                levels=["Unsupported", "Partially grounded", "Mostly grounded", "Fully grounded"],
                weight=2,
            ),
        ],
        threshold=threshold,
        system_one_model=os.getenv("JEV_MODEL", "jev-latest"),
        include_reason=True,
        async_mode=False,
    )


def build_metrics(case: dict, thresholds: dict, suite="deepeval", eval_mode="llm") -> dict:
    if suite == "jev":
        return {"jev_financial_grounding": financial_jev(thresholds["jev_financial_grounding"])}
    from deepeval.metrics import (
        AnswerRelevancyMetric,
        ContextualPrecisionMetric,
        ContextualRecallMetric,
        ContextualRelevancyMetric,
        FaithfulnessMetric,
        GEval,
        HallucinationMetric,
    )
    from deepeval.metrics.community import CitationFaithfulnessMetric
    from deepeval.test_case import SingleTurnParams

    # Explicit temperature for supported LLM judges; no LLM instantiated in system_one.
    if eval_mode == "system_one":
        model = None
    else:
        from deepeval.models import GPTModel

        model = GPTModel(model=os.getenv("DEEPEVAL_MODEL", "gpt-4.1-mini"), temperature=0)
    common = {
        "model": model,
        "eval_mode": eval_mode,
        "system_one_model": os.getenv("JEV_MODEL", "jev-latest"),
        "async_mode": False,
        "include_reason": True,
    }
    classes = {
        "faithfulness": FaithfulnessMetric,
        "answer_relevancy": AnswerRelevancyMetric,
        "contextual_precision": ContextualPrecisionMetric,
        "contextual_recall": ContextualRecallMetric,
        "contextual_relevancy": ContextualRelevancyMetric,
        "citation_faithfulness": CitationFaithfulnessMetric,
    }
    # Retrieval/grounding metrics have no evidence to grade on intended rejection cases.
    if case["should_abstain"]:
        classes = {"answer_relevancy": AnswerRelevancyMetric}
    metrics = {name: cls(threshold=thresholds[name], **common) for name, cls in classes.items()}
    # Curated reference context only. Never substitute runtime retrieval_context.
    if case["reference_context"] and not case["should_abstain"]:
        metrics["hallucination"] = HallucinationMetric(threshold=thresholds["hallucination"], **common)
    # GEval always uses an LLM. Keep system_one entirely Jev-only.
    if eval_mode != "system_one":
        metrics["financial_answer_quality"] = GEval(
            name="Financial Policy Answer Quality",
            threshold=thresholds["financial_answer_quality"],
            model=model,
            async_mode=False,
            evaluation_params=[
                SingleTurnParams.INPUT,
                SingleTurnParams.ACTUAL_OUTPUT,
                SingleTurnParams.EXPECTED_OUTPUT,
            ],
            evaluation_steps=[
                "Compare actual_output to expected_output for material omissions in answering input.",
                "Check that the response is professional and distinguishes facts from uncertainty.",
                "When expected_output requires abstention, require explicit uncertainty or refusal without invented policy details.",
            ],
        )
    return metrics


def make_test_case(case, response):
    from deepeval.test_case import LLMTestCase

    # Retriever metrics require original ranked context, not citation order.
    return LLMTestCase(
        input=case["input"],
        actual_output=response["answer"],
        expected_output=case["expected_output"],
        retrieval_context=[c["text"] for c in response["retrieval_context"]],
        context=case["reference_context"] or None,
        name=case["id"],
        tags=case["tags"],
    )


def make_citation_test_case(case, response):
    """Citation IDs identify claims in this application, not retrieval ranks.

    Build a separate test case for CitationFaithfulness: passage N is the exact
    supplied chunk backing citation N. Preserve duplicate chunks when multiple
    claims cite the same evidence. All other metrics keep original ranking.
    """
    from deepeval.test_case import LLMTestCase

    context = {row["chunk_id"]: row["text"] for row in response["retrieval_context"]}
    citations = sorted(response["citations"], key=lambda c: int(c["citation_id"]))
    if [int(c["citation_id"]) for c in citations] != list(range(1, len(citations) + 1)):
        raise ValueError("Citation IDs must be consecutive positive integers")
    passages = [context[c["chunk_id"]] for c in citations]
    return LLMTestCase(
        input=case["input"],
        actual_output=response["answer"],
        expected_output=case["expected_output"],
        retrieval_context=passages,
        context=case["reference_context"] or None,
        name=case["id"],
        tags=case["tags"],
    )


def json_value(value):
    """Lossless normalization for SDK/Pydantic question results."""
    if hasattr(value, "model_dump"):
        return json_value(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return {str(k): json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(v) for v in value]
    return value


def serialize_metric(metric, eval_mode: str) -> dict:
    score = metric.score
    return {
        "score": score,
        "passed": metric.is_successful(),
        "status": "passed" if metric.is_successful() else "failed",
        "reason": metric.reason,
        "threshold": metric.threshold,
        "eval_mode": eval_mode,
        "confidence": getattr(metric, "confidence", None),
        "score_breakdown": json_value(getattr(metric, "score_breakdown", None)),
        "system_one_fallback_reason": getattr(metric, "system_one_fallback_reason", None),
        "evaluation_cost": getattr(metric, "evaluation_cost", None),
        "evaluation_model": getattr(metric, "evaluation_model", None),
    }


def run_semantic(case, response, thresholds, suite="deepeval", eval_mode="llm"):
    mode = "system_one" if suite == "jev" else eval_mode
    names = ("jev_financial_grounding",) if suite == "jev" else SEMANTIC_NAMES
    reason = unavailable_reason(suite, eval_mode)
    results = {
        name: {
            "score": None,
            "passed": None,
            "status": "skipped",
            "reason": reason or "Not applicable to this case or mode",
            "threshold": thresholds[name],
            "eval_mode": "llm" if name == "financial_answer_quality" else mode,
            "confidence": None,
            "score_breakdown": None,
        }
        for name in names
    }
    if reason:
        return results
    test_case = make_test_case(case, response)
    try:
        metrics = build_metrics(case, thresholds, suite, eval_mode)
    except Exception as exc:
        for entry in results.values():
            entry.update(
                status="error", passed=False, reason=f"Judge initialization failed: {type(exc).__name__}"
            )
        return results
    for name, metric in metrics.items():
        try:
            metric.measure(
                make_citation_test_case(case, response) if name == "citation_faithfulness" else test_case
            )
            results[name] = serialize_metric(metric, "llm" if name == "financial_answer_quality" else mode)
        except Exception as exc:
            # Error type only: third-party exceptions can contain request content/credentials.
            results[name].update(
                status="error", passed=False, reason=f"Judge invocation failed: {type(exc).__name__}"
            )
    return results
