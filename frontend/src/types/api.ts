/** TypeScript mirror of the backend's response schemas (backend/app/schemas.py).
 *  src/test/fixtures/*.json are REAL backend responses and are type-checked against these interfaces. */

export interface HealthResponse {
  status: string; // "ok" | "degraded"
  app_name: string;
  app_version: string;
  environment: string;
  model_ready: boolean;
  database: string; // "ok" | "unavailable"
}

export interface ClassInfo {
  id: number;
  name: string;
}

export interface BundleInfo {
  model_name: string;
  bundle_version: string;
  task: string | null;
  classes: ClassInfo[];
  feature_count: number;
  features: string[];
  created_utc: string | null;
  label_provenance_documented: boolean;
  provisional_label_provenance: boolean;
  demonstration_only: boolean;
  deployable_for_decisions: boolean;
  scores_are_calibrated_probabilities: boolean;
  future_failure_prediction_supported: boolean;
  smoke_test_bundle: boolean;
  reported_test_metrics: Record<string, number> | null;
  notes: string[];
}

export interface ModelInfoResponse {
  model_ready: boolean;
  reason: string | null;
  bundle: BundleInfo | null;
}

export interface FeatureInfo {
  name: string;
  unit: string | null;
  description: string | null;
  observed_train_min: number | null;
  observed_train_max: number | null;
}

export interface FeatureListResponse {
  features: FeatureInfo[];
  note: string;
}

export interface InputWarning {
  feature: string;
  value: number;
  observed_train_min: number | null;
  observed_train_max: number | null;
  message: string;
}

export interface PredictionResult {
  prediction_id: number | null;
  record_id: string | null;
  motor_id: string | null;
  measured_at: string | null;
  predicted_condition: string;
  predicted_class_id: number;
  scores: Record<string, number>;
  scores_are_calibrated_probabilities: boolean;
  model_version: string;
  provisional_label_provenance: boolean;
  demonstration_only: boolean;
  input_warnings: InputWarning[];
  interpretation_note: string;
}

export interface BatchPredictionResponse {
  batch_id: string;
  filename: string;
  record_count: number;
  class_counts: Record<string, number>;
  model_version: string;
  provisional_label_provenance: boolean;
  demonstration_only: boolean;
  interpretation_note: string;
  results: PredictionResult[];
}

export interface ValidationIssue {
  row: number | null;
  column: string | null;
  problem: string;
}

export interface CsvValidationReport {
  valid: boolean;
  record_count: number;
  columns_found: string[];
  ignored_columns: string[];
  issues_total: number;
  issues: ValidationIssue[];
  note: string;
}

export interface HistoryItem {
  id: number;
  batch_id: string | null;
  source: string; // "single" | "csv"
  record_id: string | null;
  motor_id: string | null;
  measured_at: string | null; // naive timestamp "as recorded"
  created_at: string; // naive UTC
  predicted_condition: string;
  predicted_class_id: number;
  scores: Record<string, number>;
  model_version: string;
  provisional_label_provenance: boolean;
  demonstration_only: boolean;
}

export interface PredictionPage {
  total: number;
  limit: number;
  offset: number;
  items: HistoryItem[];
}

export interface BatchSummary {
  id: string;
  filename: string;
  record_count: number;
  created_at: string;
  model_version: string;
}

export interface BatchList {
  items: BatchSummary[];
}

/** Query filters accepted by GET /api/predictions and GET /api/reports/predictions.csv */
export interface HistoryFilters {
  motor_id?: string;
  record_id?: string;
  batch_id?: string;
  predicted_condition?: string;
  date_from?: string; // YYYY-MM-DD, prediction time (UTC date)
  date_to?: string;
  measured_from?: string; // YYYY-MM-DD, measurement time
  measured_to?: string;
}

/** Every backend error has this shape. */
export interface ApiErrorBody {
  error: { code: string; message: string; details?: unknown };
}
