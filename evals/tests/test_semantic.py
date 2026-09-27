"""Run with `deepeval test run evals/tests/test_semantic.py`.

No credentials: explicit skip. These tests never replace a judge with a mock.
"""

import json
import os

import pytest

from evals.dataset import ROOT, load_cases
from evals.metrics.semantic import build_metrics, make_citation_test_case, make_test_case, unavailable_reason

os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")


@pytest.fixture(scope="module")
def semantic_service():
    from backend.app.service import RagService
    from evals.runners.run import configuration

    service = RagService(configuration("improved"))
    service.ingest()
    return service


@pytest.mark.semantic
@pytest.mark.parametrize("case", load_cases("regression"), ids=lambda c: c["id"])
def test_deepeval_regression(case, request):
    mode = os.getenv("DEEPEVAL_EVAL_MODE", "llm")
    reason = unavailable_reason("deepeval", mode)
    if reason:
        pytest.skip(reason)
    from deepeval import assert_test

    service = request.getfixturevalue("semantic_service")
    response = service.ask(case["input"], case["user_role"], user_id="semantic-evaluator")
    thresholds = json.loads((ROOT / "evals/config.json").read_text(encoding="utf-8-sig"))["metric_thresholds"]
    metrics = build_metrics(case, thresholds, "deepeval", mode)
    citation = metrics.pop("citation_faithfulness", None)
    assert_test(make_test_case(case, response), list(metrics.values()))
    if citation is not None:
        assert_test(make_citation_test_case(case, response), [citation])


@pytest.mark.semantic
@pytest.mark.parametrize("case", load_cases("regression"), ids=lambda c: c["id"])
def test_jev_regression(case, request):
    reason = unavailable_reason("jev", "system_one")
    if reason:
        pytest.skip(reason)
    from deepeval import assert_test

    service = request.getfixturevalue("semantic_service")
    response = service.ask(case["input"], case["user_role"], user_id="jev-evaluator")
    thresholds = json.loads((ROOT / "evals/config.json").read_text(encoding="utf-8-sig"))["metric_thresholds"]
    assert_test(
        make_test_case(case, response), list(build_metrics(case, thresholds, "jev", "system_one").values())
    )
