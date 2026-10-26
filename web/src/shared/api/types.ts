export interface User {
  login: string;
  name: string;
  title: string;
  clearance: number;
  groups?: string[];
  reviewer?: boolean;
}

export interface Citation {
  paragraph_id: number;
  doc_key: string;
  title: string;
  version: number;
  tz: string;
  section: string;
  text: string;
  valid_from: string;
  valid_to: string | null;
  classification: number;
}

export interface TraceCandidate {
  paragraph_id: number;
  doc_key: string;
  version: number;
  tz: string;
  fts_rank: number | null;
  vec_rank: number | null;
  coverage: number;
  score: number;
  history: boolean;
  answers_kind: boolean;
  anchored: boolean;
}

export interface Trace {
  timings_ms: Record<string, number>;
  total_ms: number;
  redacted: string[];
  expanded_question: string;
  asked: string[] | null;
  router: { model: string; processing: string; reason: string };
  tokens: { input: number; output: number };
  cost_eur: number;
  notes: string[];
  candidates: TraceCandidate[];
}

export interface AskResult {
  query_id: number;
  outcome: "answered" | "no_answer";
  answer: string;
  citations: Citation[];
  newer: { version: number; valid_from: string; text: string } | null;
  model: string;
  as_of: string;
  trace: Trace;
}

export interface HistoryItem {
  id: number;
  at: string;
  question: string;
  as_of: string;
  outcome: "answered" | "no_answer";
  model: string;
  helpful: boolean | null;
}

export interface VersionSpan {
  version: number;
  valid_from: string;
  valid_to: string | null;
}

export interface DocumentSummary {
  doc_key: string;
  title: string;
  kind: "policy" | "circular";
  classification: number;
  owner: string | null;
  version_on: number | null;
  latest_version: number;
  versions: VersionSpan[];
}

export interface Paragraph {
  id: number;
  tz: string;
  section: string;
  text: string;
  is_history: boolean;
}

export interface DocumentVersion {
  doc_key: string;
  title: string;
  classification: number;
  owner: string | null;
  version: number;
  valid_from: string;
  valid_to: string | null;
  paragraphs: Paragraph[];
}

export interface DiffRow {
  tz: string;
  section: string;
  before: string | null;
  after: string | null;
  change: "added" | "removed" | "changed";
}

export interface ReviewItem {
  id: number;
  query_id: number;
  login: string;
  helpful: boolean;
  comment: string;
  status: string;
  created_at: string;
  question: string;
  as_of: string;
  answer: string;
  outcome: string;
  model: string;
}

export interface ImpactItem {
  id: number;
  circular: string;
  from_version: number;
  to_version: number;
  circular_tz: string;
  change: string;
  doc_key: string;
  title: string;
  tz: string;
  version: number;
  paragraph: string;
  reason: string;
  status: "open" | "resolved";
  note: string | null;
}

export interface ModelInfo {
  id: string;
  model: string;
  enabled: boolean;
  max_classification: number;
  processing: string;
}

export interface SetSummary {
  questions: number;
  accuracy: number;
  answer_accuracy: number;
  retrieval_recall: number;
  declined_correctly: number;
  answer_precision: number;
  wrong_answers: number;
  leaks: number;
  latency_ms_p50: number;
  latency_ms_p95: number;
  by_kind: Record<string, { questions: number; correct: number; accuracy: number }>;
}

export interface Evaluation {
  generated_at: string;
  sets: Record<string, SetSummary>;
  first_runs?: Record<string, SetSummary>;
}
