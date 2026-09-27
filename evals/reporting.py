"""Reports and configurable gates. Missing semantic measurements are never passes."""

from __future__ import annotations

import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path


def aggregate(results: list[dict]) -> dict:
    metrics = defaultdict(list)
    categories = defaultdict(list)
    for row in results:
        categories[row["category"]].append(row)
        for key, metric in row["metrics"].items():
            metrics[key].append(metric)
    aggregates = {}
    for key, values in metrics.items():
        scored = [v for v in values if v["score"] is not None]
        aggregates[key] = {
            "mean": statistics.mean(v["score"] for v in scored) if scored else None,
            "minimum": min(v["score"] for v in scored) if scored else None,
            "maximum": max(v["score"] for v in scored) if scored else None,
            "std": statistics.pstdev(v["score"] for v in scored) if scored else None,
            "pass_rate": sum(v["passed"] is True for v in scored) / len(scored) if scored else None,
            "failed_count": sum(v["passed"] is False for v in values),
            "scored_count": len(scored),
            "skipped_count": sum(v["status"] == "skipped" for v in values),
            "error_count": sum(v["status"] == "error" for v in values),
        }
    latencies = sorted(row["latency_ms"] for row in results)
    category_summary = {
        key: {
            "case_count": len(rows),
            "failed_count": sum(bool(r["failures"]) for r in rows),
            "pass_rate": sum(not r["failures"] for r in rows) / len(rows),
        }
        for key, rows in categories.items()
    }
    by_case = defaultdict(lambda: defaultdict(list))
    for row in results:
        for name, metric in row["metrics"].items():
            if metric["score"] is not None:
                by_case[row["case_id"]][name].append(metric["score"])
    repeatability = {
        case_id: {
            name: {"n": len(values), "mean": statistics.mean(values), "std": statistics.pstdev(values)}
            for name, values in measurements.items()
        }
        for case_id, measurements in by_case.items()
    }
    return {
        "repeatability": repeatability,
        "case_count": len(results),
        "passed_count": sum(not r["failures"] for r in results),
        "failed_count": sum(bool(r["failures"]) for r in results),
        "metrics": aggregates,
        "categories": category_summary,
        "latency": {
            "p50_ms": statistics.median(latencies),
            "p95_ms": latencies[max(0, math.ceil(0.95 * len(latencies)) - 1)],
        },
        "tokens": {
            "average_input": statistics.mean(r["token_usage"].get("input_tokens", 0) for r in results),
            "average_output": statistics.mean(r["token_usage"].get("output_tokens", 0) for r in results),
        },
        "worst_examples": [
            {
                "case_id": r["case_id"],
                "failed_metrics": [k for k, v in r["metrics"].items() if v["passed"] is False],
            }
            for r in sorted(
                results, key=lambda r: sum(v["passed"] is False for v in r["metrics"].values()), reverse=True
            )[:10]
        ],
    }


def evaluate_gates(summary: dict, config: dict) -> dict:
    groups = {}
    for group in ("critical", "quality"):
        checks = []
        for name, rule in config[group].items():
            actual = (
                summary["latency"]["p95_ms"]
                if name == "p95_latency_ms"
                else summary["metrics"].get(name, {}).get(rule.get("statistic", "mean"))
            )
            if actual is None:
                passed = False if config.get("require_semantic") else None
                status = "failed" if passed is False else "not_evaluated"
            else:
                passed = actual >= rule["threshold"] if rule["op"] == "min" else actual <= rule["threshold"]
                status = "passed" if passed else "failed"
            checks.append({"metric": name, "actual": actual, **rule, "passed": passed, "status": status})
        groups[group] = checks
    errors = sum(v["error_count"] for v in summary["metrics"].values())
    critical_ok = not any(c["passed"] is False for c in groups["critical"])
    quality_ok = not any(c["passed"] is False for c in groups["quality"])
    return {
        **groups,
        "passed": critical_ok and (quality_ok or not config["enforce_quality"]) and errors == 0,
        "quality_enforced": config["enforce_quality"],
        "require_semantic": config["require_semantic"],
        "judge_error_count": errors,
        "complete_evidence": all(c["actual"] is not None for g in groups.values() for c in g),
    }


def write_report(folder: Path, metadata: dict, results: list[dict], summary: dict):
    folder.mkdir(parents=True, exist_ok=False)
    for filename, payload in [
        ("run_metadata.json", metadata),
        ("results.json", results),
        ("summary.json", summary),
    ]:
        (folder / filename).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    with (folder / "results.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "case_id",
                "category",
                "repeat",
                "metric",
                "score",
                "passed",
                "status",
                "eval_mode",
                "reason",
                "latency_ms",
            ],
        )
        writer.writeheader()
        for row in results:
            for name, m in row["metrics"].items():
                writer.writerow(
                    {
                        "case_id": row["case_id"],
                        "category": row["category"],
                        "repeat": row["repeat"],
                        "metric": name,
                        **{k: m[k] for k in ("score", "passed", "status", "eval_mode", "reason")},
                        "latency_ms": row["latency_ms"],
                    }
                )
    failures = defaultdict(list)
    for row in results:
        for failure in row["failures"]:
            failures[failure].append(row)
    lines = [
        "# Failure analysis",
        "",
        f"Run: {metadata['run_id']}",
        "",
        "Deterministic lexical proxies diagnose the local extractive pipeline. They are not DeepEval semantic scores.",
        "",
        "## Configuration",
        "",
        "```json",
        json.dumps(metadata["configuration"], indent=2),
        "```",
    ]
    if not failures:
        lines += [
            "",
            "No failures in measured applicable checks. Skipped semantic judges do not constitute evidence of quality.",
        ]
    for category, rows in sorted(failures.items()):
        lines += ["", f"## {category} ({len(rows)})"]
        for row in rows:
            detail = {
                k: row[k]
                for k in (
                    "case_id",
                    "input",
                    "expected_output",
                    "actual_output",
                    "retrieval_context",
                    "citations",
                    "metrics",
                )
            }
            lines += [
                "",
                f"### {row['case_id']}",
                "",
                "```json",
                json.dumps(detail, indent=2, ensure_ascii=False),
                "```",
            ]
    (folder / "failure_analysis.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
