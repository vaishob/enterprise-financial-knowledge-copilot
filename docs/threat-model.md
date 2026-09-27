# Threat model

Scope: a synthetic-data internal knowledge assistant. Trust boundaries are the browser/API, identity provider/API, approved ingestion/storage, storage/model provider, and application/telemetry. No financial transaction tool or arbitrary model-driven execution is implemented.

| Threat | Attack path and impact | Implemented control | Residual risk / next control |
|---|---|---|---|
| Direct prompt injection | User requests hidden prompts, role escalation or fabricated citations | Input attack detection, server-side authorization, bounded provider output, citation verification | Pattern detection is bypassable; expand multilingual and obfuscated red-team coverage |
| Indirect prompt injection | Poisoned retrieved document tells the model to disclose data | Instruction-like sections quarantined, structured untrusted context, role filtering before generation | Novel attacks may evade detection; require approved ingestion, provenance and human document review |
| Unauthorized retrieval | User spoofs a role or queries restricted terms | Demo roles isolated to explicit demo mode; production bearer identity mapping; role predicate applied before ranking | Demo mode intentionally allows role switching; production needs verified OIDC claims and revocation |
| Cross-role leakage | Shared results, traces or evaluation reports disclose restricted evidence | No cross-user answer cache; authorized document/context routes; admin-only evaluation/trace access | Administrators can see reports across roles; deployment must restrict admin membership and backups |
| Hallucination | Model invents policy thresholds, dates or citations | Conservative extractive claims, quote membership and supplied-chunk validation, low-evidence abstention | Exact quotes can still be selected out of context; semantic evaluation and domain review remain necessary |
| Sensitive logging | Query, prompt or provider exception carries client identifiers or credentials | Query hash, metadata-only audit events, demo PII redaction, sanitized errors | Regex masking is not DLP; provider/host/APM logs need independent redaction and access control |
| Poisoned documents | Administrator ingests malicious or stale policy | Fixed approved synthetic corpus, stable metadata, inactive-version exclusion, injection quarantine | Real ingestion needs signed provenance, review workflow, malware scanning, version approval and rollback |
| Secrets exposure | Keys in Git, browser bundles, logs or container images | Environment configuration, no provider secrets in frontend, .gitignore, repository secret scan | Environment/host compromise remains; use secret manager, short-lived identity and rotation |
| Excessive model permissions | Model asks to run SQL, execute a payment or modify roles | Provider is a generation adapter only; no execution tool registry or action authority | Future tools require narrow allowlists, argument validation, audit and explicit approvals |
| Provider outage | Timeout, malformed output or throttling interrupts answering | Bounded requests and fail-closed response handling | Add circuit breakers, backoff budget, load shedding and provider SLO monitoring before deployment |
| Vector-store leakage | Raw embeddings, text or backups accessed outside API | Application role filtering; database credentials kept server-side | Embeddings are sensitive; require network isolation, encryption, database RLS and scoped operational access |
| Denial of service | Oversized prompts or repeated expensive requests | Input and context/completion limits | Distributed rate limiting, quotas and load tests are deployment requirements |
| Evaluation poisoning | Golden answers changed to conceal regressions | Versioned datasets, distinct development/regression files, metadata and failed-case reports | Add review ownership, immutable dataset releases and blinded expert adjudication |

Known attack success rate is a regression measure over the listed attacks, never proof of comprehensive security. Local demo controls are not a certification of suitability for regulated production use.

