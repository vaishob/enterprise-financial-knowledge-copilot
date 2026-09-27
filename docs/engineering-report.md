# Enterprise Financial Knowledge Copilot — engineering report

A working local RAG application and evaluation system has been implemented and exercised end to end. It is suitable for a portfolio design review with explicit quality and infrastructure limitations. All documents and organizations represented in the demo dataset are synthetic and are not official policies of any financial institution.

## What was built

Next.js and TypeScript provide chat, inspectable citations and an admin evaluation/review dashboard. FastAPI coordinates authorization, retrieval, bounded evidence, provider adapters, output verification, structured audits and OpenTelemetry instrumentation. SQLAlchemy supports a verified SQLite local profile and a PostgreSQL/pgvector deployment path. Containers, health checks, configuration validation, CI and operational documentation are included.

## Repository map

| Path | Purpose |
|---|---|
| `backend/app/` | API, identity, ingestion, retrieval, generation, guardrails, persistence and telemetry |
| `backend/tests/` | Unit, API, security, provider-contract and optional PostgreSQL integration tests |
| `frontend/` | Chat, sources, metrics, evaluation comparison and human-review interface |
| `synthetic_data/corpus.json` | 16 synthetic documents, 55 sections, an inactive version and a malicious section |
| `evals/datasets/` | Frozen 56-case dataset: 34 development and 22 regression |
| `evals/metrics/`, `evals/runners/` | Deterministic diagnostics, DeepEval/Jev, gates, unique reports and paired experiments |
| `evals/reports/` | Actual JSON/CSV measurements, metadata and failure analysis |
| `docs/` | Architecture, threats, security, deployment, evaluation, experiments and verification evidence |
| `.github/workflows/ci.yml` | Core checks, live PostgreSQL/Compose checks and optional strict semantic job |

## RAG design

Ingestion cleans and splits JSON policy sections while preserving document version, classification, role, effective date and chunk identity. Fixed token-aware and recursive structure-aware chunking are configurable. An index profile prevents silently mixing incompatible embeddings or chunking settings.

The query pipeline normalizes input, applies role/active/quarantine predicates in storage, retrieves vector and lexical candidates, reranks, and builds bounded context. PostgreSQL uses cosine vector distance plus full-text search; the local profile uses deterministic hash vectors and lexical overlap. Local extraction and OpenAI-compatible, Bedrock Converse and Ollama generators share a structured claim interface. OpenAI-compatible and optional sentence-transformer embeddings can replace local hashes.

Every accepted claim must quote a complete source span and cite a chunk supplied to generation. Evidence threshold checks, empty retrieval, input attacks, invalid claims and provider failure can cause abstention. This deliberately restrictive output contract improves traceability but reduces paraphrasing and synthesis flexibility. Citations include exact excerpt and policy metadata. Source quotations can still be irrelevant or incomplete; citation integrity alone cannot establish answer quality.

## Security

Five demo roles are filtered before evidence reaches the model. Tests cover forbidden retrieval, answers, citations and trace access. Production configuration rejects client-selected demo roles and requires signed bearer identity; enterprise OIDC/JWKS integration remains future work. Ingestion quarantines known instruction attacks. Generation separates system instructions from untrusted JSON evidence, and verifies output independently.

Audit persistence is mandatory and emits structured JSON with hashes, safe identifiers, models, decisions, tokens and timings. Raw questions, evidence bodies, credentials, hidden reasoning and provider exception strings are excluded from audit payloads. Email, phone and synthetic account masking illustrates PII control. These are demonstration controls, not complete DLP, attack-proof prompting or a substitute for database RLS and immutable audit storage.

## Evaluation

DeepEval 4.2.6 and Typesafe SDK 0.7.1 interfaces were inspected and covered by installed-API contract tests. Implemented metrics are Faithfulness, Answer Relevancy, Contextual Precision/Recall/Relevancy, community Citation Faithfulness, curated-reference Hallucination and GEval completeness/clarity/abstention. Citation judging receives contexts ordered by emitted citation IDs, while retrieval metrics preserve retrieval order.

Optional Financial RAG Grounding JevEval combines weighted Noul, Choice and Score questions about factual support, numerical/role fidelity, unsupported assumptions and abstention. Returned component values and probability/confidence/applicability fields are retained when provided. LLM, hybrid and system_one modes are separately labelled; unsupported LLM-only GEval is excluded from system_one.

The 56 cases comprise 12 direct facts, 8 multi-chunk questions, 5 similar-policy questions, 7 numeric/date questions, 5 unanswerable questions, 8 attacks, 5 RBAC cases, 3 ambiguous questions and 3 version/conflict cases. Reports preserve configuration, dataset fingerprints, prompt/metric versions, per-case evidence, category statistics, worst cases, repeated-run variance and failure analysis.

Critical gates cover leaks, attack success, citation validity, severe support/faithfulness failures and pipeline errors. Quality thresholds remain visible when advisory. `--require-semantic --enforce-quality` blocks releases with missing evidence or failed quality. An actual strict run returned the expected exit 1. DeepEval and Jev semantic metrics were skipped because credentials were unavailable; no semantic scores are claimed.

## Experiment results

The paired local run retained all 56 cases. Baseline: fixed 100-token chunks/20 overlap, vector-only top 8, no reranker. Candidate: recursive 180-token chunks/30 overlap, .45 vector/.55 lexical hybrid scoring, reranking to top 5. Both used the same local embeddings and extractive generation.

| Measurement | Baseline | Candidate |
|---|---:|---:|
| Deterministic context-precision proxy | 0.2622 | 0.2964 |
| Expected-section recall proxy | 0.9820 | 0.9820 |
| Answer-overlap proxy | 0.7183 | 0.7251 |
| Abstention accuracy | 0.9464 | 0.9464 |
| Exact quote support / citation integrity | 1.0000 / 1.0000 | 1.0000 / 1.0000 |
| Measured RBAC leakage / known attack success | 0 / 0 | 0 / 0 |
| Average estimated input tokens | 550.55 | 459.48 |
| Local latency p50 / p95, ms | 4.391 / 6.572 | 4.237 / 6.914 |

Estimated input tokens fell 16.54%; p95 latency worsened slightly. These single-host SQLite measurements exclude network model inference and are not billing or capacity estimates. Both variants retain 38 cases with diagnostic failures; candidate precision is far below the 0.75 target. Three abstention decisions are incorrect. Exact support is aided by extraction and does not demonstrate semantic faithfulness. See the [full paired experiment](experiments/baseline-vs-improved.md), including unchanged and changed outcomes.

## Verification

The final full verifier passed all 12 command checks. Pytest: 64 passed, 45 skipped. Python lint/type checks, backend package build, frontend lint/typecheck/production build, source credential-pattern scan and Compose configuration validation passed. Actual HTTP and browser checks covered answers, citations, abstention, direct/indirect attacks, admin reports, review persistence and clearing privileged UI state on role change. [Detailed commands and evidence](verification.md) record the exact scope.

## Known limitations

Docker containers and live PostgreSQL were not executed on this host. No hosted generation, embedding, DeepEval judge or Jev provider was called. CI is implemented and parsed but has not run on GitHub. No remote repository was created and no commit/deployment is claimed. Optional agentic workflows and semantic chunking were intentionally deferred.

The local system has low retrieval precision, some false abstentions and verbose extraction. A small synthetic corpus and narrow attack patterns do not establish real-world performance or security. The inspected regression set is no longer a pristine holdout. Production requires identity lifecycle integration, database isolation, migrations, approved document workflows, quotas, immutable logging, monitoring operations, dependency locking and load/resilience evidence.

## Recommended next improvements

1. Obtain expert labels, inspect failure clusters and create a fresh blind holdout; calibrate abstention and quality thresholds.
2. Run approved semantic embeddings, a reranker and real generation/judging on the same versioned corpus; improve precision and synthesis before adding agentic features.
3. Execute PostgreSQL/Compose CI and failure-path tests, then measure network latency, concurrency, actual token costs and provider failover.
4. Integrate OIDC/JWKS, least-privilege database/RLS controls, retention-aware immutable audit export and request quotas.
5. Add controlled policy ingestion/version approval, migrations, locked Python dependencies and production monitoring with expert review sampling.
