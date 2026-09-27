export const roles = ["analyst", "treasury", "risk_manager", "compliance", "admin"] as const;
export type Role = typeof roles[number];
export type Citation = {
  citation_id: string | number; document_title: string; section: string; chunk_id: string;
  excerpt: string; source: string; document_id: string; document_version?: string; effective_date?: string;
};
export type Chunk = {
  chunk_id: string; document_id: string; document_title: string; section: string; text: string;
  score?: number; vector_score?: number; keyword_score?: number; reranker_score?: number;
};
export type TokenUsage = { input_tokens: number; output_tokens: number; total_tokens: number; estimated?: boolean; estimated_cost_usd?: number | null };
export type ChatResponse = {
  answer: string; citations: Citation[]; retrieval_context: Chunk[]; trace_id: string;
  latency_ms: number; token_usage: TokenUsage; timings: Record<string, number>;
  guardrail_decisions: string[]; abstained: boolean;
};
export type Metric = {
  score: number | null; passed: boolean | null; status: string; reason?: string; threshold?: number;
  eval_mode?: string; confidence?: number | null; score_breakdown?: Record<string, unknown> | null;
};
export type EvalCase = {
  case_id: string; category: string; input: string; expected_output: string; actual_output: string;
  user_role: string; should_abstain: boolean; abstained: boolean; retrieval_context: Chunk[];
  citations: Citation[]; latency_ms: number; token_usage: TokenUsage;
  metrics: Record<string, Metric>; failures: string[];
};
export type AggregateMetric = { mean: number | null; pass_rate: number | null; failed_count: number; scored_count: number; skipped_count: number };
export type Gate = { metric: string; passed: boolean | null; actual: number | null; threshold: number };
export type EvalSummary = {
  run_id: string; case_count: number; passed_count: number; failed_count: number;
  metrics: Record<string, AggregateMetric>;
  categories: Record<string, {case_count: number; failed_count: number; pass_rate: number}>;
  latency: {p50_ms: number; p95_ms: number}; tokens: {average_input: number; average_output: number};
  gates: {passed: boolean; critical: Gate[]; quality: Gate[]};
  worst_examples?: {case_id: string; failed_metrics: string[]}[];
};
export type Metadata = Record<string, unknown>;
export type EvalRun = {run_id: string; metadata: Metadata; summary: EvalSummary};
export type Review = {case_id: string; label: "pass" | "fail" | "uncertain"; notes: string; timestamp?: string};
export type EvalDetail = EvalRun & { results: EvalCase[]; reviews: Review[] };
