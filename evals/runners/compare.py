"""Paired experiment: fixed datasets and cases, all outcomes retained."""

from __future__ import annotations

import argparse
import json

from evals.dataset import ROOT
from evals.runners.run import run


def compare(suite="deterministic", eval_mode="llm", split="all", repeats=1):
    left_path, left = run(suite=suite, eval_mode=eval_mode, split=split, variant="baseline", repeats=repeats)
    right_path, right = run(
        suite=suite, eval_mode=eval_mode, split=split, variant="improved", repeats=repeats
    )
    lmeta = json.loads((left_path / "run_metadata.json").read_text())
    rmeta = json.loads((right_path / "run_metadata.json").read_text())
    assert lmeta["dataset_sha256"] == rmeta["dataset_sha256"] and lmeta["case_ids"] == rmeta["case_ids"], (
        "Unpaired experiment is invalid"
    )
    assert lmeta["eval_mode"] == rmeta["eval_mode"], "Judging modes cannot be compared as equivalent"
    metrics = {}
    names = [
        "proxy_context_precision",
        "proxy_section_recall",
        "proxy_claim_support",
        "proxy_answer_overlap",
        "faithfulness",
        "answer_relevancy",
        "contextual_precision",
        "contextual_recall",
        "citation_faithfulness",
        "jev_financial_grounding",
        "abstention_accuracy",
        "rbac_leakage_rate",
        "attack_success_rate",
    ]
    for key in names:
        baseline = left["metrics"].get(key, {}).get("mean")
        improved = right["metrics"].get(key, {}).get("mean")
        metrics[key] = {
            "baseline": baseline,
            "improved": improved,
            "delta": None if baseline is None or improved is None else improved - baseline,
        }
    for key, a, b in [
        ("p50_latency_ms", left["latency"]["p50_ms"], right["latency"]["p50_ms"]),
        ("p95_latency_ms", left["latency"]["p95_ms"], right["latency"]["p95_ms"]),
        ("average_input_tokens", left["tokens"]["average_input"], right["tokens"]["average_input"]),
        ("average_output_tokens", left["tokens"]["average_output"], right["tokens"]["average_output"]),
    ]:
        metrics[key] = {"baseline": a, "improved": b, "delta": b - a}
    lrows = json.loads((left_path / "results.json").read_text())
    rrows = json.loads((right_path / "results.json").read_text())
    changed = []
    for a, b in zip(lrows, rrows, strict=True):
        assert (a["case_id"], a["repeat"]) == (b["case_id"], b["repeat"])
        if a["failures"] != b["failures"]:
            changed.append(
                {
                    "case_id": a["case_id"],
                    "repeat": a["repeat"],
                    "baseline_failures": a["failures"],
                    "improved_failures": b["failures"],
                }
            )
    payload = {
        "comparison_id": right["run_id"],
        "baseline_run_id": left["run_id"],
        "improved_run_id": right["run_id"],
        "dataset_sha256": lmeta["dataset_sha256"],
        "eval_mode": lmeta["eval_mode"],
        "case_count": len(lrows),
        "metrics": metrics,
        "changed_cases": changed,
        "baseline_gates": left["gates"],
        "improved_gates": right["gates"],
    }
    path = ROOT / "evals/reports" / f"comparison-{right['run_id']}.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def fmt(value):
        return "Not evaluated" if value is None else f"{value:.4f}"

    lines = [
        "# Baseline versus improved retrieval experiment",
        "",
        f"Generated from actual runs on {rmeta['timestamp']}. The full frozen {split} dataset ({len(lrows)} observations) was run in identical order through both configurations. No cases were removed.",
        "",
        "## Configurations",
        "",
        "| Configuration | Chunking | Retrieval | Final top K |",
        "|---|---|---|---|",
        "| Baseline | Fixed 100 tokens, overlap 20 | Vector-only, no reranking | 8 |",
        "| Improved candidate | Recursive 180 tokens, overlap 30 | Hybrid .45 vector / .55 lexical, reranking | 5 |",
        "",
        "Both use the same provider, corpus, query rewrite, thresholds and bounded context budget. The word improved names the candidate configuration; it is not a claim about every measurement. Chunking can have limited effect because many synthetic sections are shorter than either chunk size.",
        "",
        f"Dataset SHA-256: `{lmeta['dataset_sha256']}`. Judging mode: `{lmeta['eval_mode']}`.",
        "",
        "## Measurements",
        "",
        "The `proxy_` rows are deterministic lexical/metadata diagnostics. They are not DeepEval metrics or substitutes for a human-reviewed semantic evaluation. Missing judge credentials leave semantic measurements unevaluated. Local token estimates do not represent provider billing.",
        "",
        "| Metric | Baseline | Improved candidate | Delta |",
        "|---|---:|---:|---:|",
    ]
    lines += [
        f"| {key} | {fmt(m['baseline'])} | {fmt(m['improved'])} | {fmt(m['delta'])} |"
        for key, m in metrics.items()
    ]
    lines += [
        "",
        "## Full evidence",
        "",
        f"- [Baseline run metadata](../../evals/reports/{left_path.name}/run_metadata.json)",
        f"- [Baseline failure analysis](../../evals/reports/{left_path.name}/failure_analysis.md)",
        f"- [Candidate run metadata](../../evals/reports/{right_path.name}/run_metadata.json)",
        f"- [Candidate failure analysis](../../evals/reports/{right_path.name}/failure_analysis.md)",
        f"- [Machine-readable comparison](../../evals/reports/{path.name})",
        "",
        "## Changed cases",
        "",
        "Every changed diagnostic outcome is listed below; unchanged cases remain in both complete reports.",
    ]
    lines += [
        f"- {c['case_id']} repeat {c['repeat']}: baseline {c['baseline_failures']}; candidate {c['improved_failures']}."
        for c in changed
    ]
    lines += [
        "",
        "## Interpretation and limits",
        "",
        "More candidates can improve recall while including irrelevant sections; reranking and a smaller context can reduce that noise and tokens, but can drop supporting evidence needed for synthesis. False abstention is deliberately visible and is not rewarded as perfect grounding. Exact-span support is easier for an extractive generator than for a paraphrasing LLM, so it cannot establish production LLM faithfulness.",
        "",
        "Local latency includes Python/SQLite work on this host and excludes network model inference. It is a single-host measurement, not a service-level objective. Repeat with `--repeats 3` to inspect within-case score variance and run on a representative provider/storage stack before drawing capacity conclusions.",
        "",
        "Development and regression files were frozen before the first run. The paired aggregate includes both sets and should not be presented as an untouched independent holdout after its failure analysis has been examined. Future optimization belongs on development cases; establish a fresh reviewed holdout for model-risk approval.",
        "",
        "Semantic quality and Jev scores require credentials. The included local comparison cannot establish the proposed semantic release gates. Human review should prioritize multi-section synthesis, false abstentions and near-matching policy roles.",
    ]
    (ROOT / "docs/experiments/baseline-vs-improved.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        json.dumps({"comparison": str(path), "baseline_run": left["run_id"], "improved_run": right["run_id"]})
    )
    return payload


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--suite", choices=["deterministic", "deepeval", "jev"], default="deterministic")
    p.add_argument("--eval-mode", choices=["llm", "hybrid", "system_one"], default="llm")
    p.add_argument("--split", choices=["all", "development", "regression"], default="all")
    p.add_argument("--repeats", type=int, default=1)
    result = compare(**vars(p.parse_args()))
    raise SystemExit(0 if result["baseline_gates"]["passed"] and result["improved_gates"]["passed"] else 1)


if __name__ == "__main__":
    main()
