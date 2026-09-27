"use client";
import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Icon } from "@/components/icon";
import { useSession } from "@/components/shell";
import { api, humanize, number } from "@/lib/api";
import type { ChatResponse, Citation } from "@/lib/types";

const suggestions = [
  {label: "Data & privacy", question: "How should client data be shared securely?", icon: "shield" as const},
  {label: "People & expenses", question: "What is the employee expense submission deadline?", icon: "book" as const},
  {label: "Treasury & risk", question: "What is the escalation process when a transaction exceeds the treasury risk threshold?", icon: "chart" as const},
];
type Turn = {question: string; result: ChatResponse};
function CitedAnswer({answer, citations, onSource}: {answer: string; citations: Citation[]; onSource: (citation: Citation) => void}) {
  return <div className="answer-text">{answer.split(/(\[\d+\])/g).map((part, index) => {
    const match = /^\[(\d+)\]$/.exec(part);
    const citation = match && citations.find((item) => String(item.citation_id).replace(/[\[\]]/g, "") === match[1]);
    return citation ? <button key={index} className="inline-citation" aria-label={`Open source ${match[1]}: ${citation.document_title}`} onClick={() => onSource(citation)}>{match[1]}</button> : <span key={index}>{part}</span>;
  })}</div>;
}
function SourceDrawer({source, onClose}: {source: Citation | null; onClose: () => void}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => { if (source) ref.current?.showModal(); else ref.current?.close(); }, [source]);
  return <dialog ref={ref} className="source-dialog" aria-labelledby="source-title" onCancel={onClose} onClick={(event) => {if (event.target === event.currentTarget) onClose();}}>
    {source && <div className="source-content"><div className="row-between"><span className="eyebrow">SOURCE EVIDENCE</span><button className="icon-button" onClick={onClose} aria-label="Close source"><Icon name="close" /></button></div><span className="source-number">{String(source.citation_id).replace(/[\[\]]/g, "")}</span><h2 id="source-title">{source.document_title}</h2><p className="muted">{source.section}</p><blockquote>{source.excerpt}</blockquote><dl className="metadata-list"><dt>Document ID</dt><dd>{source.document_id}</dd><dt>Version</dt><dd>{source.document_version ?? "Not supplied"}</dd><dt>Effective date</dt><dd>{source.effective_date ?? "Not supplied"}</dd><dt>Source</dt><dd>{source.source}</dd><dt>Chunk ID</dt><dd className="mono">{source.chunk_id}</dd></dl><div className="notice"><Icon name="shield" size={18} /><p>This excerpt was supplied to the answer generator after authorization filtering. The corpus is synthetic.</p></div></div>}
  </dialog>;
}
function ResponseCard({turn, onSource}: {turn: Turn; onSource: (citation: Citation) => void}) {
  const {result} = turn;
  return <article className="turn">
    <div className="question-bubble"><span className="eyebrow">YOUR QUESTION</span><h2>{turn.question}</h2></div>
    <div className="answer-card"><div className="answer-heading"><span className="answer-logo"><Icon name="chat" size={19} /></span><strong>Knowledge Copilot</strong><span className={`badge ${result.abstained ? "warning" : "success"}`}>{result.abstained ? "Insufficient evidence" : "Evidence-backed answer"}</span></div>
      <CitedAnswer answer={result.answer} citations={result.citations} onSource={onSource} />
      {result.citations.length > 0 && <div className="sources"><span className="eyebrow">SUPPORTING SOURCES · {result.citations.length}</span><div className="source-grid">{result.citations.map((source) => <button className="source-card" key={source.citation_id} onClick={() => onSource(source)}><span className="citation-badge">{String(source.citation_id).replace(/[\[\]]/g, "")}</span><span><strong>{source.document_title}</strong><small>{source.section}</small></span><Icon name="arrow" size={16} /></button>)}</div></div>}
      <div className="response-meta"><span><Icon name="clock" size={14} />{number(result.latency_ms, 1)} ms</span><span>{number(result.token_usage.total_tokens)} {result.token_usage.estimated ? "estimated " : ""}tokens <span className="muted">({number(result.token_usage.input_tokens)} in / {number(result.token_usage.output_tokens)} out)</span></span>{result.token_usage.estimated_cost_usd != null && <span>Est. ${result.token_usage.estimated_cost_usd.toFixed(6)}</span>}<span className="trace" title={result.trace_id}>Trace <code>{result.trace_id}</code></span></div>
      <details className="developer-panel"><summary><Icon name="code" size={16} />Request diagnostics <span>Authorized context & controls</span></summary><div className="diagnostics"><h3>Guardrail decisions</h3><div className="tag-list">{result.guardrail_decisions.map((decision) => <span className="badge" key={decision}>{humanize(decision)}</span>)}</div><h3>Component timing</h3><dl className="timing-list">{Object.entries(result.timings).map(([key, value]) => <div key={key}><dt>{humanize(key.replace(/_ms$/, ""))}</dt><dd>{number(value, 2)} ms</dd></div>)}</dl><h3>Authorized retrieval context</h3>{result.retrieval_context.length === 0 ? <p className="muted">No context was supplied.</p> : result.retrieval_context.map((chunk) => <div className="context-chunk" key={chunk.chunk_id}><strong>{chunk.document_title} · {chunk.section}</strong><div className="chunk-scores"><span>Similarity {number(chunk.vector_score, 3)}</span><span>Hybrid {number(chunk.score, 3)}</span><span>Reranker {number(chunk.reranker_score, 3)}</span></div><p>{chunk.text}</p><code>{chunk.chunk_id}</code></div>)}</div></details>
    </div>
  </article>;
}
export default function ChatPage() {
  const {role} = useSession();
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [source, setSource] = useState<Citation | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  useEffect(() => () => abortRef.current?.abort(), []);
  async function ask(event: FormEvent) {
    event.preventDefault();
    if (!question.trim() || pending) return;
    setPending(true); setError("");
    const submitted = question.trim();
    const controller = new AbortController(); abortRef.current = controller;
    try {
      const result = await api<ChatResponse>("/api/v1/chat", role, {method: "POST", body: JSON.stringify({question: submitted}), signal: controller.signal});
      setTurns((old) => [...old.slice(-9), {question: submitted, result}]); setQuestion("");
    } catch (err) { if (!controller.signal.aborted) setError(err instanceof Error ? err.message : "The answer could not be loaded."); }
    finally { if (!controller.signal.aborted) setPending(false); }
  }
  function fill(value: string) {setQuestion(value); inputRef.current?.focus();}
  return <div className="chat-page">
    <div className="page-heading"><div><span className="eyebrow">YOUR KNOWLEDGE WORKSPACE</span><h1>Knowledge assistant</h1><p>Financial policy answers, with the evidence attached.</p></div>{turns.length > 0 && <button className="button secondary" onClick={() => {setTurns([]); setQuestion(""); setSource(null);}} disabled={pending}><Icon name="plus" size={16} />New session</button>}</div>
    <div className={`chat-workspace ${turns.length ? "has-turns" : ""}`}>
      {turns.length === 0 ? <div className="welcome"><div className="welcome-symbol"><Icon name="book" size={30} /><span className="sparkle">✦</span></div><span className="eyebrow">GROUNDED IN YOUR KNOWLEDGE</span><h2>Find clarity.<br /><span>Follow the evidence.</span></h2><p>Ask about policies, controls, or procedures.<br />Every answer starts with sources your role can access.</p><div className="suggestions">{suggestions.map((item) => <button key={item.label} onClick={() => fill(item.question)} className="suggestion"><span><Icon name={item.icon} size={19} /><strong>{item.label}</strong></span><p>{item.question}</p><Icon name="arrow" size={17} /></button>)}</div></div> : <div className="turns" aria-live="polite">{turns.map((turn) => <ResponseCard key={turn.result.trace_id} turn={turn} onSource={setSource} />)}</div>}
      <form className="composer" onSubmit={ask}><label className="sr-only" htmlFor="question">Ask a financial policy question</label><textarea ref={inputRef} id="question" rows={2} maxLength={2000} value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={(event) => {if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {event.preventDefault(); if (question.trim() && !pending) event.currentTarget.form?.requestSubmit();}}} placeholder="Ask a question about your internal knowledge…" disabled={pending} /><div className="composer-bottom"><span><Icon name="shield" size={14} />{humanize(role)} access<span className="composer-divider">·</span>Single-turn questions</span><button className="button primary" disabled={pending || !question.trim()} type="submit">{pending ? "Finding evidence…" : "Ask Copilot"}<Icon name="arrow" size={17} /></button></div></form>
      <div role="status" className="query-status">{pending ? "Retrieving authorized evidence and validating the answer…" : "Verify source evidence before making a policy decision. Shift + Enter for a new line."}</div>
      {error && <div className="error-message" role="alert"><strong>Unable to complete the request.</strong><p>{error}</p></div>}
    </div><SourceDrawer source={source} onClose={() => setSource(null)} />
  </div>;
}
