/** Types that mirror the backend's JSON responses (backend/app/schemas.py). */

export interface HealthResponse {
  status: string;
  app_name: string;
  app_version: string;
  environment: string;
  model_ready: boolean;
}

export interface ModelMetadata {
  model_name: string;
  model_version: string;
  trained_at?: string | null;
  positive_class: number | string;
  decision_threshold?: number | null;
  notes?: string | null;
}

export interface ModelInfoResponse {
  model_ready: boolean;
  reason?: string | null;
  metadata?: ModelMetadata | null;
  feature_count?: number | null;
}

/** Every backend error has this shape. */
export interface ApiErrorBody {
  error: { code: string; message: string; details?: unknown };
}
