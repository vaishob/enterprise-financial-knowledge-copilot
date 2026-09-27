# Security model

## Authorization

Five demonstration roles are supported: analyst, treasury, risk_manager, compliance and admin. Every chunk retains allowed-role metadata. The store restricts candidates before retrieval results enter the reranker, context builder or provider. Denials do not return document excerpts. Evaluation reports may contain evidence from multiple roles and are therefore administrative data.

`X-Demo-Role` is intentionally trusted only when demo authentication is enabled in an isolated synthetic-data environment. It provides an inspectable way to test roles; it is not authentication. Production startup rejects demo identity configuration. Signed bearer claims provide a replacement boundary, with the enterprise OIDC/JWKS integration identified as a deployment requirement.

A policy fact may intentionally appear in an unrestricted operational document as well as in a restricted treasury document. This is not a cross-role content leak if the authorized source independently contains the fact. Security tests check restricted source IDs and restricted-only facts, rather than assuming a topic itself is confidential.

## Grounding and injection

System instructions are versioned separately from retrieved text. Context is delimited data. Known attack phrases are blocked or quarantined, and authorization is enforced independently of the model. Output citation IDs must refer to chunks actually supplied to generation. Conservative claim/quote validation rejects unsupported evidence and returns insufficient-evidence answers. The system cannot execute transactions, modify access, run shell commands or claim it performed external actions.

These controls limit a defined demonstration attack surface. Keyword injection detection misses paraphrases and encoded or multilingual attacks. Quote validation does not prove semantic relevance or completeness. Treat the synthetic red-team suite as a regression corpus and expand it with human adversarial review.

## Logs, traces and review data

Query audits use a hash instead of raw user text and record trace ID, UTC time, role, retrieved document IDs, model, counts, timing, decisions and abstention. The demo redactor recognizes email addresses, telephone patterns and synthetic account identifiers. It is not production-grade DLP: formats vary, false positives/negatives occur, and the provider still needs independent data handling controls.

Administrative trace/evaluation endpoints are not ordinary-user logs. Restrict collector, database, report directory and backup access. Evaluation expected/actual answers are synthetic; introducing real content requires separate privacy review, retention and redaction. Human reviews complement automated judges and must be attributable and access controlled.

## Secrets and release control

`.env.example` has configuration placeholders and clearly marked local credentials. Actual `.env` files, runtime databases and caches are ignored. The focused scanner detects representative key/private-key patterns but does not replace a maintained secret-scanning service. CI runs deterministic authorization/injection/citation tests on ordinary changes; credentialed semantic jobs are explicit, and strict release gates must reject missing required judge results.

See [threat-model.md](threat-model.md) for residual risk and [evaluation-strategy.md](evaluation-strategy.md) for score interpretation.
