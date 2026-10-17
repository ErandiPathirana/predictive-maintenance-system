/** Shape of the saved research evaluation report (written by ml/scripts/export_evaluation_report.py). */
export interface ClassMetrics { precision: number; recall: number; f1: number; support: number }
export interface ModelMetrics {
  n: number;
  accuracy: number | null; balanced_accuracy: number | null; macro_f1: number | null; weighted_f1: number | null;
  macro_precision: number | null; macro_recall: number | null; mcc: number | null;
  roc_auc_ovr_macro: number | null; pr_auc_macro: number | null;
  per_class: Record<string, ClassMetrics>;
  confusion_matrix: number[][];
}
export interface EvaluationReport {
  schema: "pm.evaluation_report.v1";
  source: string;
  bundle_version: string | null;
  created_utc: string | null;
  test_evaluated_at_utc: string | null;
  task: string | null;
  classes: string[];
  data_origin: "real" | "synthetic" | "unknown";
  smoke_test: boolean;
  provisional_label_provenance: boolean;
  label_provenance: unknown;
  dataset: { file_name: string | null; records: number | null; motors: number | null; time_range: string[] | null };
  split: Record<string, { motors: number; records: number }> | null;
  split_strategy: string | null;
  model: ModelMetrics;
  baselines: Record<string, ModelMetrics>;
  bootstrap_ci_by_motor: unknown;
}

export type ReportCheck = { ok: true; report: EvaluationReport } | { ok: false; reason: string };

const isMatrix = (m: unknown, k: number): m is number[][] =>
  Array.isArray(m) && m.length === k && m.every((r) => Array.isArray(r) && r.length === k && r.every((v) => typeof v === "number" && v >= 0));

/** Refuses a report that does not look like our export, so the page never shows half-understood numbers. */
export function checkReport(raw: unknown): ReportCheck {
  const r = raw as Partial<EvaluationReport> | null;
  if (!r || typeof r !== "object" || r.schema !== "pm.evaluation_report.v1") return { ok: false, reason: "The file is not an evaluation report made by export_evaluation_report.py." };
  if (!Array.isArray(r.classes) || r.classes.length < 2 || !r.classes.every((c) => typeof c === "string")) return { ok: false, reason: "The report has no class list." };
  const k = r.classes.length;
  const m = r.model;
  if (!m || !isMatrix(m.confusion_matrix, k)) return { ok: false, reason: "The report's confusion matrix is missing or does not match the class list." };
  if (!m.per_class || !r.classes.every((c) => m.per_class[c] && typeof m.per_class[c].recall === "number")) return { ok: false, reason: "The report has no per-class metrics for every class." };
  for (const [name, b] of Object.entries(r.baselines ?? {})) {
    if (!isMatrix(b.confusion_matrix, k)) return { ok: false, reason: `Baseline '${name}' has an invalid confusion matrix.` };
  }
  return { ok: true, report: r as EvaluationReport };
}
