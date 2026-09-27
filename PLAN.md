# Enterprise Financial Knowledge Copilot — implementation plan

## Inspection and assumptions
The provided workspace contains no existing application. Build a new repository here. The available host is Windows with Python 3.14 and Node.js; Docker is not on PATH. Target Python 3.12+ and current Next.js. No model or judge credentials are present. All policy content is synthetic. No cloud deployment or paid model execution is required for the local path.

## Architecture
Next.js → FastAPI → RagService → input controls → authorization-filtered storage → hybrid retrieval → reranker → bounded context → provider gateway → deterministic citation/grounding checks → response and audit record.

SQLAlchemy persists chunks/embeddings, traces and human reviews. PostgreSQL/pgvector is the deployment backend; SQLite is a credential-free local development backend. Hash embeddings and an extractive local generator make security and integration testing reproducible; they are explicitly not semantic LLM equivalents. OpenAI-compatible, Bedrock and Ollama adapters remain behind interfaces. DeepEval and optional Jev judge execution are distinct from deterministic checks.

## Shared implementation contracts
- Python import root: `backend.app`; `Settings` in `backend.app.core.config`.
- Corpus: `synthetic_data/corpus.json`, an array of documents with `document_id`, `document_title`, `document_version`, `source`, `classification`, `allowed_roles`, `effective_date`, `active`, `sections` (array of `{section, text}`).
- Public service: `backend.app.service.RagService(settings=None)`, `.ingest()`, `.ask(question, role, user_id='demo')` returns a JSON-serializable dictionary.
- Chat request: `{question: string}`; demo identity supplied through `X-Demo-Role`; user cannot assign roles in production. Responses contain answer, citations, retrieval_context, trace_id, latency_ms, token_usage, timings, guardrail_decisions, abstained.
- API: POST `/api/v1/chat`, POST `/api/v1/ingest` (admin), GET `/api/v1/documents`, GET `/api/v1/evaluations`, GET `/api/v1/evaluations/{run_id}`, POST `/api/v1/evaluations/{run_id}/reviews`, GET `/api/v1/traces/{trace_id}`, `/health`, `/ready`. Evaluation and trace detail admin-only except an owner's trace if supported.
- Evaluation run directory: run_metadata.json, results.json, results.csv, summary.json, failure_analysis.md; deterministic and judge modes labelled separately.

## Milestones
1. Plan, architecture, configuration and synthetic corpus.
2. Ingestion, persistence, retrieval, providers, citation/abstention controls and security tests.
3. FastAPI contracts, audit/telemetry and integration tests.
4. Golden development/regression sets; verified current DeepEval/Jev APIs; reports, gates and failure analysis.
5. Next.js chat, evidence and evaluation UI; human review.
6. Containers, CI, reproducible commands and operational/security documentation.
7. Baseline/improved experiment, full verification, fixes and engineering report.

## Verification policy
Run deterministic tests throughout; validate actual API queries and frontend lint/typecheck/build. Inspect actual report output and compare every evaluation case without cherry-picking. Invoke credential-dependent suites and record clean skips. Attempt Docker configuration validation if a CLI is available; never claim a running PostgreSQL/container stack without executing it. Record commands, outcomes and remaining limitations in `docs/verification.md`.

## External dependencies
OpenAI/Bedrock/Ollama model endpoints, sentence-transformer weights, a judge API key, optional TYPESAFE_API_KEY, Docker and a running PostgreSQL server may be unavailable. Implement adapters and configuration; use local alternatives for the working vertical slice, explicitly preserving the limits of that evidence.

## Progress
- Repository inspected; architecture and contracts established before implementation.
- Milestones 1–6 implemented: synthetic corpus; service and API; security, provider and evaluation adapters; chat/review UI; containers, CI and documentation.
- Milestone 7 local verification completed on 2026-09-27: 12 verifier commands passed; 64 tests passed and 45 external-capability tests skipped. Actual HTTP/browser flows verified.
- Paired all-56-case experiment persisted with failure analysis. Retrieval precision remains below its quality target; strict semantic release gates correctly fail without required evidence.
- Outstanding environment-dependent acceptance: live Docker/pgvector, approved model and judge calls, remote CI and production hardening. See docs/verification.md and docs/engineering-report.md. These are not represented as completed checks.
