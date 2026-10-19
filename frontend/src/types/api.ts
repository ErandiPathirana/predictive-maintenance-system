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
  // Present on assessments and on batch rows saved since Stage 2; older rows have none.
  equipment_description?: string | null;
  recorded_by?: string | null;
  recommendation_summary?: string | null;
  ruleset_version?: string | null;
  // Follow-up information (GET /api/predictions); absent or null when there is none.
  maintenance_status?: MaintenanceStatus | null;
  maintenance_case_id?: number | null;
  report_sent_at?: string | null; // when the mail server last accepted a report (UTC)
  follows_assessment_id?: number | null; // set when this assessment is a reassessment
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
  maintenance_status?: string; // none | open | one MaintenanceStatus value
}

/** Every backend error has this shape. */
export interface ApiErrorBody {
  error: { code: string; message: string; details?: unknown };
}

// ---------- manual assessments (POST /api/assessments) ----------
export interface AssessmentRequest {
  motor_id: string;
  measured_at: string; // "YYYY-MM-DDTHH:mm" as recorded by the operator
  equipment_description?: string;
  recorded_by?: string;
  readings: Record<string, number>;
}

export interface RecommendationItem {
  priority: number;
  action: string;
  reason: string;
  responsible_role: string;
  timing: string;
  safety_note: string | null;
  source: string; // "general_guidance" | "site_approved"
  source_detail: string;
  requires_confirmation: boolean;
}

export interface RecommendationBlock {
  condition: string;
  available: boolean;
  ruleset_version: string;
  headline: string;
  items: RecommendationItem[];
  summary: string;
  disclaimer: string;
  threshold_note: string;
  site_guidance_version: string | null;
  urgent: boolean;
  return_to_service: string[];
  return_to_service_note: string | null;
}

export interface AssessmentResponse {
  saved: boolean;
  duplicate: boolean;
  assessment_id: number;
  created_at: string;
  motor_id: string | null;
  equipment_description: string | null;
  recorded_by: string | null;
  recorded_by_verified: boolean;
  measured_at: string | null;
  predicted_condition: string;
  predicted_class_id: number;
  scores: Record<string, number>;
  scores_are_calibrated_probabilities: boolean;
  model_version: string;
  provisional_label_provenance: boolean;
  demonstration_only: boolean;
  input_warnings: InputWarning[];
  readings: Record<string, number> | null;
  readings_stored: boolean;
  recommendations: RecommendationBlock;
  recommendations_regenerated: boolean;
  interpretation_note: string;
}

export interface MotorSummary {
  motor_id: string;
  record_count: number;
  last_measured_at: string | null;
}

export interface MotorList {
  items: MotorSummary[];
  note: string;
}

// ---------- report e-mail and maintenance follow-up (backend/app/schemas_workflow.py) ----------
export type MaintenanceStatus = "pending_inspection" | "maintenance_in_progress" | "repair_completed_verification_required" | "verified_closed";

export interface EmailStatus { configured: boolean; recipients_restricted: boolean; link_in_report: boolean; max_per_hour: number }
export interface EmailReportRequest { recipient: string; note?: string; readings?: Record<string, number> }
export interface EmailReportResponse {
  sent: boolean; assessment_id: number; reference: string; recipient: string; sent_at: string; readings_included: boolean; message: string;
}
export interface EmailLog { id: number; recipient: string; status: "sent" | "failed"; error_summary: string | null; created_at: string }

export interface MaintenanceUpdateRequest {
  to_status: MaintenanceStatus;
  updated_by?: string; responsible_engineer?: string; started_on?: string; completed_on?: string;
  fault_found?: string; actions_performed?: string; parts_notes?: string; comment?: string;
  verification_outcome?: "verified" | "not_verified"; reassessment_date?: string;
}
export interface MaintenanceUpdate {
  id: number; created_at: string; kind: "opened" | "update" | "reassessment"; from_status: string | null; to_status: MaintenanceStatus;
  updated_by: string | null; responsible_engineer: string | null; started_on: string | null; completed_on: string | null;
  fault_found: string | null; actions_performed: string | null; parts_notes: string | null; comment: string | null;
  verification_outcome: string | null; reassessment_date: string | null; reassessment_assessment_id: number | null;
}
export interface Reassessment {
  assessment_id: number; created_at: string; measured_at: string | null; predicted_condition: string;
  scores: Record<string, number>; readings: Record<string, number> | null;
}
export interface MaintenanceCase {
  id: number; reference: string; assessment_id: number; assessment_reference: string; motor_id: string; status: MaintenanceStatus; status_label: string;
  created_at: string; updated_at: string; allowed_next_statuses: MaintenanceStatus[]; updates: MaintenanceUpdate[]; reassessments: Reassessment[];
}
export interface MaintenanceDetail {
  assessment_id: number; predicted_condition: string; eligible: boolean; reason: string | null; case: MaintenanceCase | null; emails: EmailLog[];
  follows_assessment_id: number | null; follows_case_id: number | null;
}
