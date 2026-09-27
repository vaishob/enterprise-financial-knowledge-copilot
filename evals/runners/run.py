"""python -m evals.runners.run --suite deterministic|deepeval|jev."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from evals.dataset import ROOT, dataset_fingerprint, load_cases
from evals.metrics.deterministic import diagnose, failure_categories
from evals.metrics.semantic import run_semantic, unavailable_reason
from evals.reporting import aggregate, evaluate_gates, write_report


def configuration(name: str):
    from backend.app.core.config import Settings

    if name == "baseline":
        return Settings(
            database_url="sqlite:///:memory:",
            chunk_strategy="fixed",
            chunk_size=100,
            chunk_overlap=20,
            retrieval_top_k=8,
            rerank_top_k=8,
            hybrid_weight=1.0,
            enable_reranking=False,
        )
    if name != "improved":
        raise ValueError("Unknown configuration")
    return Settings(
        database_url="sqlite:///:memory:",
        chunk_strategy="recursive",
        chunk_size=180,
        chunk_overlap=30,
        retrieval_top_k=12,
        rerank_top_k=5,
        hybrid_weight=0.45,
        enable_reranking=True,
    )


def run(
    *,
    suite="deterministic",
    eval_mode="llm",
    split="all",
    variant="improved",
    repeats=1,
    config_path=None,
    enforce_quality=False,
    require_semantic=False,
    report_root=None,
):
    from backend.app.service import RagService

    if repeats < 1:
        raise ValueError("repeats must be positive")
    os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")
    cfg = json.loads(Path(config_path or ROOT / "evals/config.json").read_text(encoding="utf-8-sig"))
    cfg["enforce_quality"] = enforce_quality or cfg["enforce_quality"]
    cfg["require_semantic"] = require_semantic or cfg["require_semantic"]
    cases = load_cases(split)
    corpus_path = ROOT / "synthetic_data/corpus.json"
    corpus = json.loads(corpus_path.read_text(encoding="utf-8-sig"))
    settings = configuration(variant)
    service = RagService(settings)
    ingest = service.ingest()
    stamp = datetime.now(timezone.utc)
    run_id = stamp.strftime("%Y%m%dT%H%M%S") + "-" + suite + "-" + variant + "-" + uuid.uuid4().hex[:8]
    results = []
    skip_reason = unavailable_reason(suite, eval_mode) if suite != "deterministic" else None
    if skip_reason:
        print(f"SKIPPED semantic judges: {skip_reason}")
    for repeat in range(1, repeats + 1):
        for case in cases:
            response = service.ask(case["input"], case["user_role"], user_id="offline-evaluator")
            metrics = diagnose(case, response, corpus)
            if suite != "deterministic":
                metrics.update(run_semantic(case, response, cfg["metric_thresholds"], suite, eval_mode))
            failures = failure_categories(case, response, metrics)
            if response["latency_ms"] > cfg["quality"]["p95_latency_ms"]["threshold"]:
                failures.append("latency regression")
            if any(m["status"] == "error" for m in metrics.values()):
                failures.append("judge error")
            if any(
                m["passed"] is False and k in {"answer_relevancy", "financial_answer_quality"}
                for k, m in metrics.items()
            ):
                failures.append("semantic answer quality")
            results.append(
                {
                    "case_id": case["id"],
                    "category": case["category"],
                    "input": case["input"],
                    "expected_output": case["expected_output"],
                    "actual_output": response["answer"],
                    "user_role": case["user_role"],
                    "should_abstain": case["should_abstain"],
                    "abstained": response["abstained"],
                    "retrieval_context": response["retrieval_context"],
                    "citations": response["citations"],
                    "latency_ms": response["latency_ms"],
                    "timings": response.get("timings", {}),
                    "token_usage": response["token_usage"],
                    "trace_id": response["trace_id"],
                    "guardrail_decisions": response.get("guardrail_decisions", []),
                    "metrics": metrics,
                    "failures": failures,
                    "repeat": repeat,
                }
            )
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, stderr=subprocess.DEVNULL, text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    packages = {}
    for package in ("deepeval", "typesafe-sdk"):
        try:
            packages[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            packages[package] = None
    source_digest = hashlib.sha256()
    for source in sorted([*(ROOT / "backend").rglob("*.py"), *(ROOT / "evals").rglob("*.py")]):
        source_digest.update(source.relative_to(ROOT).as_posix().encode())
        source_digest.update(source.read_bytes())
    meta = {
        "source_sha256": source_digest.hexdigest(),
        "run_id": run_id,
        "timestamp": stamp.isoformat(),
        "git_commit": commit,
        "dataset_version": "synthetic-financial-golden-v1",
        "dataset_split": split,
        "dataset_sha256": dataset_fingerprint(cases),
        "case_ids": [c["id"] for c in cases],
        "corpus_sha256": hashlib.sha256(corpus_path.read_bytes()).hexdigest(),
        "metric_version": cfg["version"],
        "suite": suite,
        "eval_mode": "deterministic"
        if suite == "deterministic"
        else "system_one"
        if suite == "jev"
        else eval_mode,
        "judge_model": os.getenv("DEEPEVAL_MODEL", "gpt-4.1-mini")
        if suite == "deepeval" and eval_mode != "system_one"
        else None,
        "jev_model": os.getenv("JEV_MODEL", "jev-latest")
        if suite == "jev" or eval_mode in {"hybrid", "system_one"}
        else None,
        "configuration": {
            **settings.public_metadata(),
            "query_rewrite_enabled": settings.query_rewrite_enabled,
            "temperature": settings.temperature,
            "max_completion_tokens": settings.max_completion_tokens,
        },
        "configuration_name": variant,
        "thresholds": cfg,
        "repeats": repeats,
        "packages": packages,
        "ingestion": ingest,
        "semantic_status": "not_requested"
        if suite == "deterministic"
        else "skipped"
        if skip_reason
        else "executed",
        "semantic_skip_reason": skip_reason,
        "measurement_limitations": "Local lexical/metadata scores are proxies. Token counts and costs follow the configured provider; local token estimates are not provider billing.",
    }
    summary = {"run_id": run_id, **aggregate(results)}
    summary["gates"] = evaluate_gates(summary, cfg)
    folder = Path(report_root or ROOT / "evals/reports") / run_id
    write_report(folder, meta, results, summary)
    print(
        json.dumps(
            {
                "run_id": run_id,
                "cases": len(results),
                "diagnostic_failures": summary["failed_count"],
                "gates_passed": summary["gates"]["passed"],
                "semantic_status": meta["semantic_status"],
            }
        )
    )
    return folder, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=["deterministic", "deepeval", "jev"], default="deterministic")
    parser.add_argument("--eval-mode", choices=["llm", "hybrid", "system_one"], default="llm")
    parser.add_argument("--split", choices=["development", "regression", "all"], default="all")
    parser.add_argument("--variant", choices=["baseline", "improved"], default="improved")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--config-path")
    parser.add_argument("--enforce-quality", action="store_true")
    parser.add_argument("--require-semantic", action="store_true")
    args = parser.parse_args()
    _, summary = run(**vars(args))
    raise SystemExit(0 if summary["gates"]["passed"] else 1)


if __name__ == "__main__":
    main()
