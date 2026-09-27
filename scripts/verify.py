"""Portable local verification; records skipped unavailable capabilities."""
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
def main():
    os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")
    npm = "npm.cmd" if os.name == "nt" else "npm"
    checks = [
        ("python lint", [sys.executable, "-m", "ruff", "check", "backend", "evals", "scripts"], ROOT),
        ("python typecheck", [sys.executable, "-m", "mypy", "backend"], ROOT),
        ("tests", [sys.executable, "-m", "pytest"], ROOT),
        ("backend package build", [sys.executable, "-m", "build", "--no-isolation"], ROOT),
        ("source credential scan", [sys.executable, "-m", "scripts.scan_secrets"], ROOT),
        ("deterministic regression gates", [sys.executable, "-m", "evals.runners.run", "--suite", "deterministic", "--split", "regression"], ROOT),
        ("DeepEval run", [sys.executable, "-m", "evals.runners.run", "--suite", "deepeval"], ROOT),
        ("Jev run", [sys.executable, "-m", "evals.runners.run", "--suite", "jev"], ROOT),
        ("frontend lint", [npm, "run", "lint"], ROOT / "frontend"),
        ("frontend typecheck", [npm, "run", "typecheck"], ROOT / "frontend"),
        ("frontend build", [npm, "run", "build"], ROOT / "frontend"),
    ]
    docker = shutil.which("docker")
    standalone_compose = shutil.which("docker-compose")
    if docker:
        checks.append(("Docker config", [docker, "compose", "config", "--quiet"], ROOT))
    if not docker and standalone_compose:
        checks.append(("Docker config", [standalone_compose, "config", "--quiet"], ROOT))
    outcomes = []
    for name, command, cwd in checks:
        print(f"Running {name}", flush=True)
        result = subprocess.run(command, cwd=cwd, check=False)
        outcomes.append({"check": name, "command": command, "exit_code": result.returncode})
    output = {"timestamp": datetime.now(timezone.utc).isoformat(), "checks": outcomes,
              "docker_status": "config validated; engine not inferred" if docker or standalone_compose else "SKIPPED: Docker CLI/engine unavailable",
              "semantic_note": "Successful optional commands may contain skipped metrics; inspect their run reports."}
    (ROOT / "docs" / "verification-results.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    return int(any(item["exit_code"] for item in outcomes))
if __name__ == "__main__":
    raise SystemExit(main())
