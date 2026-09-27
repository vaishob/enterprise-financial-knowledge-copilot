# Baseline versus improved retrieval experiment

Generated from actual runs on 2026-09-27T03:01:12.003930+00:00. The full frozen all dataset (56 observations) was run in identical order through both configurations. No cases were removed.

## Configurations

| Configuration | Chunking | Retrieval | Final top K |
|---|---|---|---|
| Baseline | Fixed 100 tokens, overlap 20 | Vector-only, no reranking | 8 |
| Improved candidate | Recursive 180 tokens, overlap 30 | Hybrid .45 vector / .55 lexical, reranking | 5 |

Both use the same provider, corpus, query rewrite, thresholds and bounded context budget. The word improved names the candidate configuration; it is not a claim about every measurement. Chunking can have limited effect because many synthetic sections are shorter than either chunk size.

Dataset SHA-256: `d1361b7e1c1e51ec470ae26f89d4b607eda881495365a198a7bd9a2e6676f501`. Judging mode: `deterministic`.

## Measurements

The `proxy_` rows are deterministic lexical/metadata diagnostics. They are not DeepEval metrics or substitutes for a human-reviewed semantic evaluation. Missing judge credentials leave semantic measurements unevaluated. Local token estimates do not represent provider billing.

| Metric | Baseline | Improved candidate | Delta |
|---|---:|---:|---:|
| proxy_context_precision | 0.2622 | 0.2964 | 0.0342 |
| proxy_section_recall | 0.9820 | 0.9820 | 0.0000 |
| proxy_claim_support | 1.0000 | 1.0000 | 0.0000 |
| proxy_answer_overlap | 0.7183 | 0.7251 | 0.0068 |
| faithfulness | Not evaluated | Not evaluated | Not evaluated |
| answer_relevancy | Not evaluated | Not evaluated | Not evaluated |
| contextual_precision | Not evaluated | Not evaluated | Not evaluated |
| contextual_recall | Not evaluated | Not evaluated | Not evaluated |
| citation_faithfulness | Not evaluated | Not evaluated | Not evaluated |
| jev_financial_grounding | Not evaluated | Not evaluated | Not evaluated |
| abstention_accuracy | 0.9464 | 0.9464 | 0.0000 |
| rbac_leakage_rate | 0.0000 | 0.0000 | 0.0000 |
| attack_success_rate | 0.0000 | 0.0000 | 0.0000 |
| p50_latency_ms | 4.3910 | 4.2365 | -0.1545 |
| p95_latency_ms | 6.5720 | 6.9140 | 0.3420 |
| average_input_tokens | 550.5536 | 459.4821 | -91.0714 |
| average_output_tokens | 139.2857 | 140.3214 | 1.0357 |

## Full evidence

- [Baseline run metadata](../../evals/reports/20260927T030111-deterministic-baseline-fbe65b1a/run_metadata.json)
- [Baseline failure analysis](../../evals/reports/20260927T030111-deterministic-baseline-fbe65b1a/failure_analysis.md)
- [Candidate run metadata](../../evals/reports/20260927T030112-deterministic-improved-ff471d47/run_metadata.json)
- [Candidate failure analysis](../../evals/reports/20260927T030112-deterministic-improved-ff471d47/failure_analysis.md)
- [Machine-readable comparison](../../evals/reports/comparison-20260927T030112-deterministic-improved-ff471d47.json)

## Changed cases

Every changed diagnostic outcome is listed below; unchanged cases remain in both complete reports.
- fin-001 repeat 1: baseline ['irrelevant retrieval', 'incomplete answer']; candidate ['irrelevant retrieval'].

## Interpretation and limits

More candidates can improve recall while including irrelevant sections; reranking and a smaller context can reduce that noise and tokens, but can drop supporting evidence needed for synthesis. False abstention is deliberately visible and is not rewarded as perfect grounding. Exact-span support is easier for an extractive generator than for a paraphrasing LLM, so it cannot establish production LLM faithfulness.

Local latency includes Python/SQLite work on this host and excludes network model inference. It is a single-host measurement, not a service-level objective. Repeat with `--repeats 3` to inspect within-case score variance and run on a representative provider/storage stack before drawing capacity conclusions.

Development and regression files were frozen before the first run. The paired aggregate includes both sets and should not be presented as an untouched independent holdout after its failure analysis has been examined. Future optimization belongs on development cases; establish a fresh reviewed holdout for model-risk approval.

Semantic quality and Jev scores require credentials. The included local comparison cannot establish the proposed semantic release gates. Human review should prioritize multi-section synthesis, false abstentions and near-matching policy roles.
