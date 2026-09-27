# Evaluation strategy

All documents and organizations represented in the demo dataset are synthetic and are not official policies of any financial institution.

This subsystem separates deterministic software invariants, lexical diagnostics, probabilistic semantic judges and human review. DeepEval is the semantic evaluation framework; its actual metrics are never replaced with locally fabricated scores. A missing judge credential produces `score: null`, `passed: null`, `status: skipped` and a recorded reason. A judge or pipeline error is a failure, not a skip or successful abstention.

## Frozen offline datasets

The golden set contains **56 manually specified cases**: 12 direct factual, 8 multi-chunk synthesis, 5 similar-policy disambiguation, 7 numerical/date, 5 unanswerable, 8 adversarial, 5 RBAC, 3 ambiguous and 3 versioning/reconcilable-conflict cases. References point to specific synthetic document sections, not runtime retrieval results. Each case records the role, expected answer, source IDs/sections, curated context, expected abstention and attack indicators where relevant.

The development set contains 34 cases and the regression set 22. Both JSON files and their SHA-256 hashes were frozen before the first run. The loader rejects accidental drift. Change expected behavior only through an explicit reviewed dataset version change, never to make a failing implementation pass. Development cases are for tuning; regression is for release review. Once failures from this demonstration regression set have been investigated, it must not be advertised as an untouched independent holdout. Obtain a new human-reviewed holdout for a production decision.

## Scoring components and end-to-end behavior

Each runner ingests the corpus into a fresh database, invokes the same `RagService.ask()` used by the API and preserves the full response. Retrieval diagnostics use the ordered authorized context actually sent to generation. Generator metrics judge the returned answer. Citation tests validate both software identifiers and semantic attribution. Abstention and known attacks are checked against explicit expectations. The metrics isolate failure symptoms; an end-to-end run does not by itself establish causality between pipeline stages.

The local path uses hash embeddings and an extractive generator. Deterministic scores are deliberately named `proxy_*`:

| Diagnostic | Definition and limitation |
|---|---|
| `proxy_context_precision` | Fraction of supplied chunks matching a gold document/section; can penalize relevant but unlisted supporting sections. |
| `proxy_section_recall` | Fraction of gold sections included; section presence alone does not establish a complete answer. |
| `proxy_claim_support` | Exact normalized sentence containment in supplied evidence; works for this extractive contract, misses entailment/contradiction, penalizes legitimate paraphrases. |
| `proxy_answer_overlap` | Reference-answer token recall; rewards word overlap, not correctness. |
| `citation_integrity` | Cited chunk IDs were supplied, markers map, non-abstentions have evidence. This is not semantic citation faithfulness. |
| `abstention_accuracy` | Agreement between actual and expected abstention, including false abstention. |
| `rbac_leakage_rate` | Unauthorized context/citation IDs, restricted copied spans and curated forbidden outputs. |
| `attack_success_rate` | Successful known attacks divided by the 8 attempted attacks; non-attack cases are inapplicable. |
| `pipeline_error_rate` | Fail-closed runtime errors; a broken pipeline must not pass by abstaining. |

The security diagnostics supplement dedicated backend security tests, including prompt inspection and audit isolation. Zero observed attacks is evidence about these known inputs only, not a proof that arbitrary indirect injection is prevented.

## Current DeepEval integration

API paths and signatures were verified against **installed DeepEval 4.2.6** and **typesafe-sdk 0.7.1** on 26 September 2026. `evals/tests/test_evaluation.py` checks the import paths, arguments, question models and actual serialization types without making paid calls. Versions are recorded in every run. Upgrade the pins only with a reviewed compatibility run.

| Metric | Component / failure diagnosed | Demo threshold |
|---|---|---:|
| FaithfulnessMetric | Generator assertions unsupported by or inconsistent with runtime evidence | ≥ .85 |
| AnswerRelevancyMetric | Off-topic answer content | ≥ .80 |
| ContextualPrecisionMetric | Relevant retrieval ranked behind irrelevant context | ≥ .75 |
| ContextualRecallMetric | Reference-answer information missing from retrieval | ≥ .80 |
| ContextualRelevancyMetric | Irrelevant material in retrieved context | ≥ .70 |
| CitationFaithfulnessMetric | A marker supports the wrong claim or points to unsupported evidence | ≥ .90 |
| HallucinationMetric | Contradictions with curated ground-truth context | ≤ .10 |
| GEval financial answer quality | Material omissions, professional clarity and nuanced abstention | ≥ .80 |

These are illustrative acceptance criteria chosen to make omissions and unsupported policy claims visible. They are not universal bank thresholds. Calibrate against independently labelled domain-expert data and asymmetric error costs before deployment. A citation attribution error is costly; this community metric is binary in relevant modes, so a .90 threshold effectively requires its passing verdict.

The installed import is `from deepeval.metrics.community import CitationFaithfulnessMetric`, not the default namespace. Application citation IDs enumerate claims, while the metric interprets `[N]` as passage N. The adapter therefore creates **a separate citation test case** with citation-ordered supplied chunks, preserving duplicates when multiple claims cite one chunk. Retriever metrics retain the original ranking. Hallucination receives only curated `reference_context` in the test case `context` field; runtime retrieval is never substituted.

Source contracts: [Faithfulness](https://deepeval.com/docs/metrics-faithfulness), [Answer Relevancy](https://deepeval.com/docs/metrics-answer-relevancy), [Contextual Precision](https://deepeval.com/docs/metrics-contextual-precision), [Contextual Recall](https://deepeval.com/docs/metrics-contextual-recall), [Contextual Relevancy](https://deepeval.com/docs/metrics-contextual-relevancy), [Citation Faithfulness community import and numbering](https://deepeval.com/docs/metrics-citation-faithfulness), [Hallucination curated context](https://deepeval.com/docs/metrics-hallucination), [GEval](https://deepeval.com/docs/metrics-llm-evals).

## Jev as an optional first-class judge

`financial_jev()` uses `JevEval`, `SingleTurnParams.INPUT`, `ACTUAL_OUTPUT` and `RETRIEVAL_CONTEXT`. Its three `Noul` propositions assess claim support, exact financial details and unsupported assumptions with weight 3 each. A weight-2 `Choice` asks how insufficient evidence is handled, with an explicit inapplicable option. A weight-2 `Score` grades Unsupported → Partially grounded → Mostly grounded → Fully grounded. These weights emphasize dangerous unsupported details over presentation.

The installed Jev constructor uses `system_one_model`; it does not take an LLM `model`. The report preserves its aggregate, per-question value, weight, applicability, probabilities and confidence, plus fallback reasons for standard metrics in hybrid mode. Confidence describes decisiveness, not truth. It never replaces human validation. Missing `TYPESAFE_API_KEY` skips only dependent measurements. Jev calls are not simulated and no Jev score is fabricated.

Verified upstream: [JevEval arguments and question primitives](https://deepeval.com/docs/metrics-jev-eval), [upstream JevEval implementation](https://github.com/confident-ai/deepeval/blob/main/deepeval/metrics/jev_eval/jev_eval.py), [TypeSafe primitives](https://docs.typesafe.ai/primitives), [official Python SDK](https://github.com/typesafe-ai/typesafe-sdk-python), [typesafe-sdk 0.7.1 release](https://pypi.org/project/typesafe-sdk/0.7.1/).

## Judging modes and repeatability

`llm` uses an LLM throughout. `hybrid` uses an LLM for extraction/reasons and Jev for supported decision steps, with upstream fallback behavior captured. `system_one` uses Jev over the raw case and needs no LLM credential. GEval is always LLM-based and is omitted in system_one runs. Custom JevEval is always Jev-based. See the verified [DeepEval eval mode contract](https://deepeval.com/docs/evaluation-eval-modes).

Store mode alongside every metric and keep judging mode, model version, rubric, dataset and prompt fixed for longitudinal comparison. An identical numeric scale does not make modes interchangeable. LLM judges use temperature 0 but are not perfectly deterministic. `--repeats 3` retains every observation and reports per-case mean/std in `summary.repeatability`; overall metric standard deviation is across observed scores and should not be mistaken for within-case uncertainty.

## Commands

Run from the repository root after installing `.[dev,eval,jev]`:

```sh
python -m pytest evals/tests -q
python -m evals.runners.run --suite deterministic --split all
python -m evals.runners.run --suite deepeval --eval-mode llm
python -m evals.runners.run --suite deepeval --eval-mode hybrid
python -m evals.runners.run --suite deepeval --eval-mode system_one
python -m evals.runners.run --suite jev
python -m evals.runners.run --suite deepeval --split regression --repeats 3 --enforce-quality --require-semantic
deepeval test run evals/tests/test_semantic.py
python -m evals.runners.compare
```

The DeepEval CLI runs both regression pathways; absent keys produce explicit pytest skips. The report runner persists skipped semantic entries even without keys. `OPENAI_API_KEY` is the LLM **judge** credential, independent of application `LLM_API_KEY`. `DEEPEVAL_MODEL` selects the judge (default `gpt-4.1-mini`); `JEV_MODEL` defaults to `jev-latest`. `TYPESAFE_API_KEY` enables Jev. Provider-specific data governance review is required before substituting real internal documents.

## Reports, gates and failure analysis

Every run gets a timestamp/UUID directory containing metadata, JSON/CSV results, summary and grouped failure analysis. Metadata records git commit if available, a Python source fingerprint, package versions, dataset/corpus hashes, case IDs, generation/embedding/judge configuration, prompt version, chunk settings, retrieval/reranking, thresholds, judging mode and skip reasons. It excludes secrets. Reports include category counts, metric means, pass rates, minima, failed/skipped/error counts, worst cases, latency percentiles and provider token accounting. The local token counts are estimates, not billable model usage. API access to reports and human labels is restricted to admin.

`evals/config.json` separates critical gates from quality gates. RBAC leakage, attack success and pipeline errors must equal zero; citation integrity must equal one. Severe grounding uses the **minimum** scored faithfulness/exact-support value, avoiding an average that hides one severe failure. Critical failures and judge errors always cause a nonzero process exit. The lexical precision/recall/overlap diagnostics also have explicit advisory thresholds, so local quality enforcement works without a judge. Quality gates are advisory by default and become blocking with `--enforce-quality`. Skipped semantic gates are `not_evaluated`, never passed. `--require-semantic` makes missing evidence fail configured gates; use it with quality enforcement for release approval.

Failure analysis retains questions, expected/actual answers, ordered retrieved chunks, citations, reasons, scores and configuration, grouped into retrieval miss, irrelevant retrieval, ranking issue, unsupported generation, wrong citation, abstention error, authorization failure, injection success, runtime failure and latency regression. A run can pass critical controls while having many advisory retrieval/quality failures; the dashboard displays both.

## Human review and eventual production monitoring

The admin evaluation API persists pass/fail/uncertain labels and notes for a run/case. Domain experts should inspect uncertain Jev outputs, numerical thresholds, role names, conflicting versions, low precision and false abstentions. Review labels supplement rather than overwrite original machine measurements. Production should sample authorized/redacted traces under approved retention controls, stratify by role/document/version, investigate drift, and maintain incident-linked regression cases. Do not export raw restricted context to a judge without institutional approval.

The synthetic corpus is small; reference labels were authored for a demonstration and have not been validated by financial-policy experts. Judges can share systematic model biases, probability confidence is imperfect, lexical metrics are shallow, and observed local performance cannot predict PostgreSQL/provider behavior. Use these results diagnostically, with the full [paired experiment](experiments/baseline-vs-improved.md), rather than treating one average as release authority.
