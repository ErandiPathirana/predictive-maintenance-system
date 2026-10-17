/** Types that mirror the backend's JSON responses (backend/app/schemas.py). */

export interface HealthResponse {
  status: string; // "ok" or "degraded"
  app_name: string;
  app_version: string;
  environment: string;
  model_ready: boolean;
  database: string; // "ok" or "unavailable"
}

export interface ClassInfo {
  id: number;
  name: string;
}

export interface BundleInfo {
  model_name: string;
  bundle_version: string;
  task?: string | null;
  classes: ClassInfo[];
  feature_count: number;
  features: string[];
  created_utc?: string | null;
  label_provenance_documented: boolean;
  provisional_label_provenance: boolean;
  demonstration_only: boolean;
  deployable_for_decisions: boolean;
  scores_are_calibrated_probabilities: boolean;
  future_failure_prediction_supported: boolean;
  smoke_test_bundle: boolean;
  reported_test_metrics?: Record<string, number> | null;
  notes: string[];
}

export interface ModelInfoResponse {
  model_ready: boolean;
  reason?: string | null;
  bundle?: BundleInfo | null;
}

/** Every backend error has this shape. */
export interface ApiErrorBody {
  error: { code: string; message: string; details?: unknown };
}
