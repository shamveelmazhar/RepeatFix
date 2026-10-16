// Mirrors docs/API.md — keep in sync.

export type Source = "asrs" | "sdr" | "photo" | "text";

export interface JobCard {
  id: string;
  source: Source;
  date: string | null;
  aircraft_type: string;
  registration: string | null;
  ata_chapter: string;
  ata_name?: string;
  component: string;
  symptom: string;
  failure_mode: string;
  action_taken: string;
  parts: string[];
  downtime_hours: number | null;
  raw_text: string;
}

export interface RepeatRow {
  asset: string;
  aircraft_type: string;
  ata_chapter: string;
  ata_name?: string;
  failure_mode: string;
  count: number;
  mtbf_days: number | null;
  downtime_hours: number;
  card_ids: string[];
}

export type GroupBy = "aircraft" | "component";

export interface Hypothesis {
  cause: string;
  confidence: "high" | "medium" | "low";
  evidence_card_ids: string[];
}

export interface Procedure {
  doc: string;
  section: string;
  page: number | null;
  page_label?: string | null; // printed page, e.g. "9-12"
  snippet: string;
  url?: string | null;
  citation?: string; // full reference, e.g. "AC 43.13-1B, Chapter 9, Section 1, par. 9-14 (...), page 9-12"
}

export interface WorkOrder {
  title: string;
  asset: string | null;
  steps: string[];
  parts: string[];
  est_hours: number | null;
  status: "draft" | "approved";
}

export interface RepeatHistory {
  count: number;
  first_date: string | null;
  last_date: string | null;
  card_ids: string[];
}

export interface AssistResponse {
  id: string;
  structured: JobCard;
  similar: { card: JobCard; score: number }[];
  hypotheses: Hypothesis[];
  procedures: Procedure[];
  work_order: WorkOrder;
  repeat_history?: RepeatHistory | null;
  timing: { total_ms: number; tokens_per_s: number | null };
  /** True when the backend returned a saved answer instead of calling the model. */
  cached?: boolean;
}

export interface FailureMode {
  code: string;
  label: string;
  ata_chapter: string;
}

export interface Metrics {
  cards_processed: number;
  extraction_field_accuracy: number | null;
  labelled_cards: number;
  repeat_groups_found: number;
  p50_latency_ms: number | null;
  tokens_per_s: number | null;
  cost_per_100_cards_usd: number | null;
  gpu: string;
  model: string;
}
