"use client";
import { useEffect, useState } from "react";
import { useSession } from "@/components/shell";
import { Icon } from "@/components/icon";
import { api, humanize, number, percent } from "@/lib/api";
import type { EvalCase, EvalDetail, EvalRun, Metadata, Review } from "@/lib/types";

function metadataValue(metadata: Metadata, key: string) {
  const value = metadata[key];
  return value === undefined || value === null ? "Not recorded" : typeof value === "object" ? JSON.stringify(value) : String(value);
}
function comparable(a: EvalRun, b: EvalRun) {
  return ["eval_mode", "dataset_sha256", "judge_model", "jev_model", "metric_version"].every((key) => JSON.stringify(a.metadata[key]) === JSON.stringify(b.metadata[key])) && a.run_id !== b.run_id;
}
function CaseInspector({item, runId, initialReview}: {item: EvalCase; runId: string; initialReview?: Review}) {
  const {role} = useSession();
  const [label, setLabel] = useState<Review["label"]>(initialReview?.label ?? "uncertain");
  const [notes, setNotes] = useState(initialReview?.notes ?? "");
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  async function save() {
    setSaving(true); setError(""); setSaved(false);
    try {await api(`/api/v1/evaluations/${encodeURIComponent(runId)}/reviews`, role, {method: "POST", body: JSON.stringify({case_id: item.case_id, label, notes})}); setSaved(true);}
    catch(err) {setError(err instanceof Error ? err.message : "Review could not be saved.");}
    finally {setSaving(false);}
  }
  return <div className="case-inspector"><div className="case-question"><span className="eyebrow">{item.case_id} · {humanize(item.user_role)}</span><h3>{item.input}</h3><div className="tag-list">{item.failures.map((failure) => <span key={failure} className="badge danger">{humanize(failure)}</span>)}<span className="badge">Expected abstention: {item.should_abstain ? "yes" : "no"}</span><span className="badge">Actual abstention: {item.abstained ? "yes" : "no"}</span></div></div>
    <div className="answer-comparison"><div><h4>Expected answer</h4><p>{item.expected_output}</p></div><div><h4>Actual answer</h4><p>{item.actual_output}</p></div></div>
    <h4>Metric scores & reasons</h4><div className="case-metrics">{Object.entries(item.metrics).map(([key, metric]) => <div className="case-metric" key={key}><div className="row-between"><strong>{humanize(key)}</strong><span className={`badge ${metric.status === "passed" ? "success" : metric.status === "failed" ? "danger" : ""}`}>{metric.score == null ? humanize(metric.status) : percent(metric.score)}</span></div><p>{metric.reason ?? "No reason supplied."}</p><small>Threshold {metric.threshold == null ? "—" : percent(metric.threshold)} · Mode {metric.eval_mode ?? "not recorded"}{metric.confidence != null ? ` · Confidence ${percent(metric.confidence)}` : ""}</small>{metric.score_breakdown && <details><summary>Question values, applicability & probability details</summary><pre>{JSON.stringify(metric.score_breakdown, null, 2)}</pre></details>}</div>)}</div>
    <details className="inspection-details"><summary>Retrieved context · {item.retrieval_context.length} chunks</summary>{item.retrieval_context.map((chunk, index) => <div className="context-chunk" key={chunk.chunk_id ?? index}><strong>{chunk.document_title ?? chunk.document_id} · {chunk.section}</strong><p>{chunk.text}</p><code>{chunk.chunk_id}</code></div>)}</details>
    <details className="inspection-details"><summary>Citations · {item.citations.length}</summary>{item.citations.map((citation) => <div className="context-chunk" key={citation.citation_id}><strong>[{citation.citation_id}] {citation.document_title} · {citation.section}</strong><p>{citation.excerpt}</p><code>{citation.chunk_id}</code></div>)}</details>
    <section className="review-form"><div><h4>Human review</h4><p className="muted">Capture a domain reviewer’s assessment alongside automated scores.</p></div><div className="review-labels" role="group" aria-label="Human review decision">{(["pass", "fail", "uncertain"] as const).map((value) => <button type="button" key={value} aria-pressed={value === label} className={`button ${value === label ? "selected" : "secondary"}`} onClick={() => {setLabel(value); setSaved(false);}}>{humanize(value)}</button>)}</div><label htmlFor={`notes-${item.case_id}`}>Reviewer notes</label><textarea id={`notes-${item.case_id}`} value={notes} maxLength={3000} rows={3} onChange={(event) => {setNotes(event.target.value); setSaved(false);}} placeholder="Add context, evidence concerns, or a follow-up recommendation…" /><div className="row-between"><span role="status" className="muted">{saved ? "Review saved." : initialReview ? "Existing review loaded." : "Reviews are stored by the backend."}</span><button className="button primary" disabled={saving} onClick={save}>{saving ? "Saving…" : "Save review"}<Icon name="check" size={16} /></button></div>{error && <p className="error-message" role="alert">{error}</p>}</section>
  </div>;
}
function Dashboard() {
  const {role} = useSession();
  const [runs, setRuns] = useState<EvalRun[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [detail, setDetail] = useState<EvalDetail | null>(null);
  const [compareId, setCompareId] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState<"failed" | "all">("failed");
  useEffect(() => {
    const controller = new AbortController();
    api<{runs: EvalRun[]} | EvalRun[]>("/api/v1/evaluations", role, {signal: controller.signal}).then((result) => {const items = Array.isArray(result) ? result : result.runs; setRuns(items); setSelectedId((current) => items.some((run) => run.run_id === current) ? current : items[0]?.run_id ?? ""); setError("");}).catch((err) => {if (!controller.signal.aborted) setError(err.message);}).finally(() => {if (!controller.signal.aborted) setLoading(false);});
    return () => controller.abort();
  }, [role, refresh]);
  useEffect(() => {
    if (!selectedId) return;
    const controller = new AbortController();
    api<EvalDetail>(`/api/v1/evaluations/${encodeURIComponent(selectedId)}`, role, {signal: controller.signal}).then((result) => {setDetail(result); setError("");}).catch((err) => {if (!controller.signal.aborted) setError(err.message);});
    return () => controller.abort();
  }, [selectedId, role, refresh]);
  const current = detail?.run_id === selectedId ? detail : null;
  const comparison = runs.find((run) => run.run_id === compareId && current && comparable(current, run));
  const cases = current?.results.filter((item) => filter === "all" || item.failures.length > 0 || Object.values(item.metrics).some((metric) => metric.passed === false)) ?? [];
  return <>
    <div className="evaluation-toolbar"><label>Evaluation run<select value={selectedId} onChange={(event) => {setSelectedId(event.target.value); setCompareId("");}} disabled={!runs.length}>{!runs.length && <option value="">No reports available</option>}{runs.map((run) => <option key={run.run_id} value={run.run_id}>{run.run_id}</option>)}</select></label><button className="button secondary" onClick={() => {setLoading(true); setRefresh((value) => value + 1);}} disabled={loading}><Icon name="refresh" size={16} />Refresh reports</button></div>
    {error && <div className="error-message" role="alert">{error}</div>}
    {loading && <div className="empty-state" role="status">Loading persisted evaluation reports…</div>}
    {!loading && runs.length === 0 && !error && <div className="empty-state"><Icon name="chart" size={32} /><h2>No evaluation reports yet</h2><p>Run the evaluation CLI to generate a report, then refresh this page.<br />Only actual persisted results appear here.</p><code>make eval</code></div>}
    {selectedId && !current && !loading && !error && <div className="empty-state" role="status">Loading evaluation detail…</div>}
    {current && <>
      <section className="run-overview"><div className="row-between"><div><span className="eyebrow">PERSISTED RUN</span><h2>Evaluation overview</h2></div><span className={`badge ${current.summary.gates.passed ? "success" : "danger"}`}>{current.summary.gates.passed ? "Enforced gates passed" : "Gate review required"}</span></div>{current.metadata.semantic_status === "skipped" && <p className="notice" role="status">Semantic judges were skipped. These results do not establish semantic release quality.</p>}<div className="run-config"><div><span>Evaluation mode</span><strong>{metadataValue(current.metadata,"eval_mode")}</strong></div><div><span>Dataset version</span><strong>{metadataValue(current.metadata,"dataset_version")}</strong></div><div><span>Generation model</span><strong>{metadataValue((current.metadata.configuration ?? {}) as Metadata,"llm_model")}</strong></div><div><span>Judge model</span><strong>{metadataValue(current.metadata,"judge_model")}</strong></div></div><details className="run-metadata"><summary>Full reproducibility metadata</summary><pre>{JSON.stringify(current.metadata, null, 2)}</pre></details></section>
      <div className="stat-grid"><div className="stat-card"><span>Evaluated cases</span><strong>{number(current.summary.case_count)}</strong><small>{number(current.summary.passed_count)} passed · {number(current.summary.failed_count)} failed</small></div><div className="stat-card"><span>Median latency</span><strong>{number(current.summary.latency.p50_ms, 1)}<em>ms</em></strong><small>P95 {number(current.summary.latency.p95_ms, 1)} ms</small></div><div className="stat-card"><span>Average input tokens</span><strong>{number(current.summary.tokens.average_input, 1)}</strong><small>Per evaluated request</small></div><div className="stat-card"><span>Average output tokens</span><strong>{number(current.summary.tokens.average_output, 1)}</strong><small>See metadata for token measurement mode</small></div></div>
      <section className="panel"><div className="section-heading"><div><h2>Quality & safety metrics</h2><p>Means, pass rates, and coverage from this run. Skipped judges are not scores.</p></div><label className="compare-selector">Compare with<select value={comparison?.run_id ?? ""} onChange={(event) => setCompareId(event.target.value)}><option value="">No comparison</option>{runs.filter((run) => comparable(current, run)).map((run) => <option key={run.run_id} value={run.run_id}>{run.run_id}</option>)}</select></label></div>
        <div className="metric-grid">{Object.entries(current.summary.metrics).map(([key, metric]) => {const baseline = comparison?.summary.metrics[key]; const delta = typeof metric.mean === "number" && typeof baseline?.mean === "number" ? metric.mean - baseline.mean : null; return <div className="metric-card" key={key}><div className="row-between"><h3>{humanize(key)}</h3><strong>{percent(metric.mean)}</strong></div><div className="metric-track"><span style={{width: `${Math.max(0, Math.min(100, (metric.mean ?? 0)*100))}%`}} /></div><div className="metric-meta"><span>{percent(metric.pass_rate)} pass rate</span><span>{metric.failed_count} failed</span></div><small>{metric.scored_count} scored · {metric.skipped_count} skipped{delta != null ? ` · Δ ${delta >= 0 ? "+" : ""}${(delta * 100).toFixed(1)} pp` : ""}</small></div>;})}</div>
        {comparison && <div className="comparison-note"><strong>Compared with {comparison.run_id}</strong><p>Same recorded dataset fingerprint, metric version, judge and evaluation mode. Configuration changes and measurement noise can affect results. Positive deltas indicate higher scores, including metrics where lower is better.</p><div className="tag-list"><span className="badge">P50 Δ {number(current.summary.latency.p50_ms - comparison.summary.latency.p50_ms, 2)} ms</span><span className="badge">Input tokens Δ {number(current.summary.tokens.average_input - comparison.summary.tokens.average_input, 1)}</span><span className="badge">Output tokens Δ {number(current.summary.tokens.average_output - comparison.summary.tokens.average_output, 1)}</span></div></div>}
      </section>
      <div className="evaluation-columns"><section className="panel"><h2>Category breakdown</h2><div className="table-scroll"><table><thead><tr><th scope="col">Category</th><th scope="col">Cases</th><th scope="col">Failed</th><th scope="col">Pass rate</th></tr></thead><tbody>{Object.entries(current.summary.categories).map(([key, category]) => <tr key={key}><th scope="row">{humanize(key)}</th><td>{category.case_count}</td><td>{category.failed_count}</td><td>{percent(category.pass_rate)}</td></tr>)}</tbody></table></div></section><section className="panel"><h2>Regression gates</h2><p className="muted">Thresholds are run-specific demonstration settings.</p>{(["critical", "quality"] as const).map((type) => <div className="gate-group" key={type}><span className="eyebrow">{type.toUpperCase()}</span>{current.summary.gates[type].map((gate) => <div className="gate-row" key={gate.metric}><span>{humanize(gate.metric)}<small>Actual {number(gate.actual, 3)} · threshold {number(gate.threshold, 3)}</small></span><span className={`badge ${gate.passed === null ? "" : gate.passed ? "success" : "danger"}`}>{gate.passed === null ? "Not evaluated" : gate.passed ? "Pass" : "Fail"}</span></div>)}</div>)}</section></div>
      <section className="panel"><div className="section-heading"><div><h2>Case review</h2><p>Inspect the evidence behind a result and record a human assessment.</p></div><div className="segmented" role="group" aria-label="Case filter"><button className={filter === "failed" ? "selected" : ""} onClick={() => setFilter("failed")}>Failures</button><button className={filter === "all" ? "selected" : ""} onClick={() => setFilter("all")}>All cases</button></div></div>{cases.length === 0 ? <div className="no-failures"><Icon name="check" size={21} /><span>No failed cases in this run. Select “All cases” to inspect successful examples.</span></div> : <div className="case-list">{cases.map((item) => <details className="case-item" key={`${current.run_id}-${item.case_id}`}><summary><span className={`case-dot ${item.failures.length ? "failed" : ""}`} /><span><strong>{item.input}</strong><small>{item.case_id} · {humanize(item.category)}</small></span><Icon name="chevron" size={16} /></summary><CaseInspector item={item} runId={current.run_id} initialReview={current.reviews?.find((review) => review.case_id === item.case_id)} /></details>)}</div>}</section>
    </>}
  </>;
}
export default function EvaluationsPage() {
  const {role} = useSession();
  return <div className="evaluations-page"><div className="page-heading"><div><span className="eyebrow">MEASURE. INSPECT. IMPROVE.</span><h1>Evaluations</h1><p>Quality is a collection of evidence, not a single score.</p></div><span className="badge admin"><Icon name="shield" size={13} />ADMIN WORKSPACE</span></div>{role === "admin" ? <Dashboard /> : <section className="access-panel"><div className="welcome-symbol"><Icon name="shield" size={29} /></div><h2>Evaluation access is restricted</h2><p>Reports contain answers and retrieved context across roles.<br />Choose the Admin demonstration role to review evaluation results.</p><span className="badge">Current role: {humanize(role)}</span></section>}</div>;
}
