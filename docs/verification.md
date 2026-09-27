# Verification record

Verified locally on 27 September 2026. Final full verifier timestamp: 2026-09-27T08:15:59.185173+00:00.

The credential-free vertical slice runs with SQLite, 384-dimensional hash embeddings and an extractive generator. This record does not assert a production deployment or successful cloud-model evaluation.

## Executed checks

| Command or check | Observed result |
|---|---|
| `python -m scripts.verify` | All 12 command checks exit 0; [machine-readable record](verification-results.json) |
| `python -m ruff check backend evals scripts` | Passed |
| `python -m mypy backend` | Passed, 33 source files |
| `python -m pytest` | 64 passed, 45 skipped, 11 upstream deprecation warnings |
| `python -m build --no-isolation` | Backend source distribution and wheel built |
| `python -m scripts.scan_secrets` | Pattern scan passed; not a comprehensive secret audit |
| `python -m evals.runners.run --suite deterministic --split regression` | Enforced deterministic critical gates passed |
| `python -m evals.runners.run --suite deepeval` | Reports written; credential-dependent metrics skipped with null scores |
| `python -m evals.runners.run --suite jev` | Reports written; absent Typesafe key handled cleanly |
| DeepEval CLI `test run evals/tests/test_semantic.py` | 44 tests skipped; exit 0, no semantic scores |
| `python -m evals.runners.compare` | Both configurations executed on all 56 cases; [complete comparison](experiments/baseline-vs-improved.md) |
| Frontend `npm run lint`, `npm run typecheck`, `npm run build` | All passed; production routes generated |
| Standalone official Compose `config --quiet` | Passed; Docker engine unavailable |
| GitHub Actions YAML parse | Passed; workflow itself has not run remotely |
| Strict semantic release command below | Exit 1 as expected: unavailable semantic evidence and unmet quality target block release |

The 45 pytest skips are one live PostgreSQL integration test, 22 DeepEval cases and 22 Jev cases. The 11 warnings originate in upstream DeepEval/Python 3.14 compatibility paths. The DeepEval command used its installed CLI entry function because this host's target-directory package installation did not create its console script: `python -c "from deepeval.cli.main import app; app()" test run evals/tests/test_semantic.py`.

```sh
python -m evals.runners.run --suite deepeval --split regression --require-semantic --enforce-quality
```

Its [persisted summary](../evals/reports/20260927T081613-deepeval-improved-d69611f4/summary.json) records the intentional gate failure. A successful optional command does not mean that skipped judges passed. Ordinary local gates enforce leakage, known attacks, citation integrity, exact quote support and pipeline errors; advisory quality failures remain visible.

## HTTP and browser evidence

The API and frontend were started as local processes on ports 8000 and 3000. Ingestion persisted the synthetic corpus. `/health` and `/ready` returned 200. A non-admin evaluation request returned 403.

[HTTP smoke results](http-smoke-results.json) preserve actual responses for a treasury threshold question, an unsupported price question, an unauthorized liquidity question, direct prompt injection and the benign section of the indirect-injection exercise. Unsupported, unauthorized and direct-attack requests abstained. Authorized responses had valid source citations; the malicious section was excluded.

Browser verification exercised question submission, cited source inspection, the admin evaluation dashboard, failed-case inspection and a persisted uncertain human-review label. The review explicitly says it is a UI test, not domain-expert adjudication. Switching to analyst cleared the privileged view and displayed the access restriction. Captured browser error/warning logs were empty. [Source inspection screenshot](source-evidence.png) provides visual evidence.

## Environment and reproducibility boundaries

Host: Windows, Python 3.14.7, Node.js 24.21.0. Deployment images target Python 3.12 and Node.js 24; CI targets Python 3.12 and Node.js 22. No Docker engine, PostgreSQL server or hosted model/judge credentials were available. Adapter tests use mocked wire contracts; they do not establish live provider behavior. No AWS, on-prem or GitHub deployment was executed.

Host-only workarounds were required for restricted Windows process/DLL behavior: a task-local Python environment with pure-Python SQLAlchemy/mypy, a temporary directory permission compatibility shim, PowerShell as npm's script shell, and official standalone Compose for config validation. These helpers are outside the deliverable repository. Next.js uses worker threads with two workers and still performs TypeScript checking. The portable setup is documented in the README; no dependency installation or cloud action is required to inspect reports.

## Outstanding acceptance evidence

Run the actual Compose stack and live pgvector test on a Docker-enabled machine. Configure approved embedding/generation and judge endpoints, run all semantic modes, calibrate thresholds with domain reviewers, and require strict gates before release. The current candidate has 38 of 56 cases with at least one diagnostic failure and fails the context-precision quality target. These are retained in the reports, not waived as passing quality. The local project is reviewable; the complete production-style acceptance matrix remains partially unverified.
