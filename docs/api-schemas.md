# API request and response schemas

Generated from the running application (`backend/scripts/generate_api_docs.py`). Interactive version: `/docs`.

## Endpoints

| Method | Path | Summary |
|---|---|---|
| GET | `/api/health` | Is the API running? |
| GET | `/api/model-info` | Describe the loaded model bundle |
| GET | `/api/features` | List the model inputs, in the order the model expects |
| GET | `/api/template.csv` | Download an empty CSV template with the correct columns |
| POST | `/api/uploads/validate` | Check a CSV file without predicting or storing anything |
| POST | `/api/predict` | Predict the condition class for ONE set of sensor readings |
| POST | `/api/predict/batch` | Predict the condition class for every record in an uploaded CSV |
| POST | `/api/assessments` | Assess ONE motor from manually entered readings, get recommendations, and save the result |
| GET | `/api/assessments/{assessment_id}` | One stored assessment with its recommendations |
| GET | `/api/motors` | Motor IDs seen in stored predictions |
| GET | `/api/predictions` | Prediction history (newest first), filter by motor, batch, class or date |
| GET | `/api/predictions/{prediction_id}` | One stored prediction |
| GET | `/api/batches` | Recent CSV upload batches |
| GET | `/api/reports/predictions.csv` | Export prediction results to CSV (same filters as the history) |
| GET | `/api/email-status` | Whether report e-mail is set up (never returns credentials) |
| POST | `/api/assessments/{assessment_id}/email-report` | E-mail the report of an Alert or Danger assessment (only when a person asks) |
| GET | `/api/assessments/{assessment_id}/maintenance` | Maintenance case, report e-mails and reassessment links for an assessment |
| POST | `/api/assessments/{assessment_id}/maintenance-case` | Open a follow-up case (status Pending Inspection) for an Alert or Danger assessment |
| POST | `/api/maintenance-cases/{case_id}/updates` | Record a status change or note on a case (appended; earlier entries are never edited) |
| POST | `/api/maintenance-cases/{case_id}/reassessments` | Link a later assessment of the same motor to the case (the new assessment is saved separately, as usual) |

## Schemas

### AssessmentRequest

A manual motor assessment. The same strict checks and preprocessing as CSV rows are applied to `readings`.

| Field | Type | Required | Description |
|---|---|---|---|
| `motor_id` | string | yes | Motor reference (letters, digits, . _ -). New IDs are allowed if they match this pattern. |
| `measured_at` | date-time | yes | When the reading was taken (ISO 8601). Required for assessments. |
| `equipment_description` | string or null | no | Optional name or description of the equipment. |
| `recorded_by` | string or null | no | Optional free-text name or initials. NOT verified: the API has no user login. |
| `readings` | dict[str, integer or number] | yes | One numeric value per model input, keyed by feature name (see GET /api/features). Text, booleans, NaN and infinity are rejected. |

### AssessmentResponse

| Field | Type | Required | Description |
|---|---|---|---|
| `saved` | boolean | yes | True only after the database confirmed the save. |
| `duplicate` | boolean | yes | True when this is a replay of an earlier submission with the same Idempotency-Key. Nothing new was saved. |
| `assessment_id` | integer | yes |  |
| `created_at` | date-time | yes |  |
| `motor_id` | string or null | yes |  |
| `equipment_description` | string or null | yes |  |
| `recorded_by` | string or null | yes |  |
| `recorded_by_verified` | boolean | no |  |
| `measured_at` | date-time or null | yes |  |
| `predicted_condition` | string | yes |  |
| `predicted_class_id` | integer | yes |  |
| `scores` | dict[str, number] | yes |  |
| `scores_are_calibrated_probabilities` | boolean | no |  |
| `model_version` | string | yes |  |
| `provisional_label_provenance` | boolean | yes |  |
| `demonstration_only` | boolean | yes |  |
| `input_warnings` | list[InputWarning] | no |  |
| `readings` | dict[str, number] or null | no | The validated readings. Returned on creation, and later only if the server stores readings. |
| `readings_stored` | boolean | yes |  |
| `recommendations` | RecommendationBlock | yes |  |
| `recommendations_regenerated` | boolean | no | True when an older record had no stored recommendations and they were rebuilt from the stored condition. |
| `interpretation_note` | string | no |  |

### BatchList

| Field | Type | Required | Description |
|---|---|---|---|
| `items` | list[BatchSummary] | yes |  |

### BatchPredictionResponse

| Field | Type | Required | Description |
|---|---|---|---|
| `batch_id` | string | yes |  |
| `filename` | string | yes |  |
| `record_count` | integer | yes |  |
| `class_counts` | dict[str, integer] | yes |  |
| `model_version` | string | yes |  |
| `provisional_label_provenance` | boolean | yes |  |
| `demonstration_only` | boolean | yes |  |
| `interpretation_note` | string | no |  |
| `results` | list[PredictionResult] | yes |  |

### BatchSummary

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes |  |
| `filename` | string | yes |  |
| `record_count` | integer | yes |  |
| `created_at` | date-time | yes |  |
| `model_version` | string | yes |  |

### Body_predict_batch_api_predict_batch_post

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | string | yes | A .csv file with the columns from GET /api/template.csv |

### Body_validate_upload_api_uploads_validate_post

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | string | yes | A .csv file with the columns from GET /api/template.csv |

### BundleInfo

| Field | Type | Required | Description |
|---|---|---|---|
| `model_name` | string | yes |  |
| `bundle_version` | string | yes |  |
| `task` | string or null | yes |  |
| `classes` | list[ClassInfo] | yes |  |
| `feature_count` | integer | yes |  |
| `features` | list[string] | yes |  |
| `created_utc` | string or null | yes |  |
| `label_provenance_documented` | boolean | yes |  |
| `provisional_label_provenance` | boolean | yes |  |
| `demonstration_only` | boolean | yes |  |
| `deployable_for_decisions` | boolean | yes |  |
| `scores_are_calibrated_probabilities` | boolean | no |  |
| `future_failure_prediction_supported` | boolean | yes |  |
| `smoke_test_bundle` | boolean | yes |  |
| `reported_test_metrics` | object or null | no |  |
| `notes` | list[string] | yes |  |

### ClassInfo

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | integer | yes |  |
| `name` | string | yes |  |

### CsvValidationReport

| Field | Type | Required | Description |
|---|---|---|---|
| `valid` | boolean | yes |  |
| `record_count` | integer | yes |  |
| `columns_found` | list[string] | yes |  |
| `ignored_columns` | list[string] | yes |  |
| `issues_total` | integer | yes |  |
| `issues` | list[ValidationIssue] | yes |  |
| `note` | string | no |  |

### EmailLogOut

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | integer | yes |  |
| `recipient` | string | yes |  |
| `status` | string | yes |  |
| `error_summary` | string or null | no |  |
| `created_at` | date-time | yes |  |

### EmailReportRequest

| Field | Type | Required | Description |
|---|---|---|---|
| `recipient` | string | yes | One e-mail address. |
| `note` | string or null | no | Optional note from the sender. |
| `readings` | dict[str, integer or number] or null | no | Only needed when the server does not store readings. They are checked against the saved result and are NOT stored. |

### EmailReportResponse

| Field | Type | Required | Description |
|---|---|---|---|
| `sent` | boolean | yes |  |
| `assessment_id` | integer | yes |  |
| `reference` | string | yes |  |
| `recipient` | string | yes |  |
| `sent_at` | date-time | yes |  |
| `readings_included` | boolean | yes |  |
| `message` | string | yes |  |

### EmailStatus

| Field | Type | Required | Description |
|---|---|---|---|
| `configured` | boolean | yes | False until the administrator sets SMTP_HOST and SMTP_FROM. |
| `recipients_restricted` | boolean | yes | True when only recipients at approved domains are accepted. |
| `link_in_report` | boolean | yes | True when the report contains a link to the assessment. |
| `max_per_hour` | integer | yes |  |

### ErrorBody

| Field | Type | Required | Description |
|---|---|---|---|
| `code` | string | yes |  |
| `message` | string | yes |  |
| `details` | any or null | no |  |

### ErrorResponse

| Field | Type | Required | Description |
|---|---|---|---|
| `error` | ErrorBody | yes |  |

### FeatureInfo

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes |  |
| `unit` | string or null | no |  |
| `description` | string or null | no |  |
| `observed_train_min` | number or null | no |  |
| `observed_train_max` | number or null | no |  |

### FeatureListResponse

| Field | Type | Required | Description |
|---|---|---|---|
| `features` | list[FeatureInfo] | yes |  |
| `note` | string | no |  |

### HealthResponse

| Field | Type | Required | Description |
|---|---|---|---|
| `status` | string | yes | 'ok' or 'degraded' (model or database unavailable). |
| `app_name` | string | yes |  |
| `app_version` | string | yes |  |
| `environment` | string | yes |  |
| `model_ready` | boolean | yes |  |
| `database` | string | yes |  |

### HistoryItem

| Field | Type | Required | Description |
|---|---|---|---|
| `equipment_description` | string or null | no |  |
| `recorded_by` | string or null | no | Free text typed by the user. NOT a verified identity. |
| `recommendation_summary` | string or null | no |  |
| `ruleset_version` | string or null | no |  |
| `id` | integer | yes |  |
| `batch_id` | string or null | yes |  |
| `source` | string | yes |  |
| `record_id` | string or null | yes |  |
| `motor_id` | string or null | yes |  |
| `measured_at` | date-time or null | yes |  |
| `created_at` | date-time | yes |  |
| `predicted_condition` | string | yes |  |
| `predicted_class_id` | integer | yes |  |
| `scores` | dict[str, number] | yes |  |
| `model_version` | string | yes |  |
| `provisional_label_provenance` | boolean | yes |  |
| `demonstration_only` | boolean | yes |  |
| `maintenance_status` | string or null | no | Status of the follow-up case opened for this assessment, if any. |
| `maintenance_case_id` | integer or null | no |  |
| `report_sent_at` | date-time or null | no | When the mail server last accepted a report for this assessment (UTC). |
| `follows_assessment_id` | integer or null | no | Set when this assessment is a reassessment linked to an earlier case. |

### InputWarning

| Field | Type | Required | Description |
|---|---|---|---|
| `feature` | string | yes |  |
| `value` | number | yes |  |
| `observed_train_min` | number or null | yes |  |
| `observed_train_max` | number or null | yes |  |
| `message` | string | yes |  |

### MaintenanceCaseOut

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | integer | yes |  |
| `reference` | string | yes |  |
| `assessment_id` | integer | yes |  |
| `assessment_reference` | string | yes |  |
| `motor_id` | string | yes |  |
| `status` | string | yes |  |
| `status_label` | string | yes |  |
| `created_at` | date-time | yes |  |
| `updated_at` | date-time | yes |  |
| `allowed_next_statuses` | list[string] | yes |  |
| `updates` | list[MaintenanceUpdateOut] | yes |  |
| `reassessments` | list[ReassessmentOut] | yes |  |

### MaintenanceDetail

| Field | Type | Required | Description |
|---|---|---|---|
| `assessment_id` | integer | yes |  |
| `predicted_condition` | string | yes |  |
| `eligible` | boolean | yes | True when a follow-up case can be opened (Alert or Danger, with a motor ID, and none yet). |
| `reason` | string or null | no | Why a case cannot be opened, when eligible is false and there is no case. |
| `case` | MaintenanceCaseOut or null | no |  |
| `emails` | list[EmailLogOut] | no |  |
| `follows_assessment_id` | integer or null | no | Set when this assessment is a reassessment linked to an earlier case. |
| `follows_case_id` | integer or null | no |  |

### MaintenanceUpdateOut

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | integer | yes |  |
| `created_at` | date-time | yes |  |
| `kind` | string | yes |  |
| `from_status` | string or null | yes |  |
| `to_status` | string | yes |  |
| `updated_by` | string or null | yes |  |
| `responsible_engineer` | string or null | yes |  |
| `started_on` | date or null | yes |  |
| `completed_on` | date or null | yes |  |
| `fault_found` | string or null | yes |  |
| `actions_performed` | string or null | yes |  |
| `parts_notes` | string or null | yes |  |
| `comment` | string or null | yes |  |
| `verification_outcome` | string or null | yes |  |
| `reassessment_date` | date or null | yes |  |
| `reassessment_assessment_id` | integer or null | yes |  |

### MaintenanceUpdateRequest

| Field | Type | Required | Description |
|---|---|---|---|
| `to_status` | string | yes |  |
| `updated_by` | string or null | no | Free text. NOT a verified identity: there is no login. |
| `responsible_engineer` | string or null | no |  |
| `started_on` | date or null | no |  |
| `completed_on` | date or null | no |  |
| `fault_found` | string or null | no |  |
| `actions_performed` | string or null | no |  |
| `parts_notes` | string or null | no |  |
| `comment` | string or null | no |  |
| `verification_outcome` | string or null | no |  |
| `reassessment_date` | date or null | no |  |

### ModelInfoResponse

| Field | Type | Required | Description |
|---|---|---|---|
| `model_ready` | boolean | yes |  |
| `reason` | string or null | no |  |
| `bundle` | BundleInfo or null | no |  |

### MotorList

| Field | Type | Required | Description |
|---|---|---|---|
| `items` | list[MotorSummary] | yes |  |
| `note` | string | no |  |

### MotorSummary

| Field | Type | Required | Description |
|---|---|---|---|
| `motor_id` | string | yes |  |
| `record_count` | integer | yes |  |
| `last_measured_at` | date-time or null | yes |  |

### PredictionPage

| Field | Type | Required | Description |
|---|---|---|---|
| `total` | integer | yes |  |
| `limit` | integer | yes |  |
| `offset` | integer | yes |  |
| `items` | list[HistoryItem] | yes |  |

### PredictionResult

| Field | Type | Required | Description |
|---|---|---|---|
| `prediction_id` | integer or null | no |  |
| `record_id` | string or null | yes |  |
| `motor_id` | string or null | yes |  |
| `measured_at` | date-time or null | yes |  |
| `predicted_condition` | string | yes | Predicted condition class. Not a confirmed failure. |
| `predicted_class_id` | integer | yes |  |
| `scores` | dict[str, number] | yes | Model output score per class (sum to 1). Not calibrated probabilities. |
| `scores_are_calibrated_probabilities` | boolean | no |  |
| `model_version` | string | yes |  |
| `provisional_label_provenance` | boolean | yes |  |
| `demonstration_only` | boolean | yes |  |
| `input_warnings` | list[InputWarning] | no |  |
| `interpretation_note` | string | no |  |

### ReassessmentLinkRequest

| Field | Type | Required | Description |
|---|---|---|---|
| `assessment_id` | integer | yes |  |
| `reassessment_date` | date or null | no |  |

### ReassessmentOut

| Field | Type | Required | Description |
|---|---|---|---|
| `assessment_id` | integer | yes |  |
| `created_at` | date-time | yes |  |
| `measured_at` | date-time or null | yes |  |
| `predicted_condition` | string | yes |  |
| `scores` | dict[str, number] | yes |  |
| `readings` | dict[str, number] or null | no | Only when the server stores readings. |

### RecommendationBlock

| Field | Type | Required | Description |
|---|---|---|---|
| `condition` | string | yes |  |
| `available` | boolean | yes | False when the model returned a class the rules do not cover. Nothing is invented then. |
| `ruleset_version` | string | yes |  |
| `headline` | string | yes |  |
| `items` | list[RecommendationItem] | yes |  |
| `summary` | string | yes |  |
| `disclaimer` | string | yes |  |
| `threshold_note` | string | yes |  |
| `site_guidance_version` | string or null | no |  |
| `urgent` | boolean | yes |  |
| `return_to_service` | list[string] | yes | Questions to settle before return to service. Not pass/fail criteria. |
| `return_to_service_note` | string or null | no |  |

### RecommendationItem

| Field | Type | Required | Description |
|---|---|---|---|
| `priority` | integer | yes |  |
| `action` | string | yes |  |
| `reason` | string | yes |  |
| `responsible_role` | string | yes |  |
| `timing` | string | yes | Immediate safety review, Prompt engineering assessment, Planned maintenance review or Routine monitoring. No exact deadlines. |
| `safety_note` | string or null | no |  |
| `source` | string | yes | 'general_guidance' or 'site_approved' |
| `source_detail` | string | yes |  |
| `requires_confirmation` | boolean | yes |  |

### SinglePredictionRequest

| Field | Type | Required | Description |
|---|---|---|---|
| `record_id` | string or null | no | Your own record reference (letters, digits, . _ -). |
| `motor_id` | string or null | no | Motor reference (letters, digits, . _ -). |
| `measured_at` | date-time or null | no | When the reading was taken (ISO 8601). Stored for history only; not a model input. |
| `readings` | dict[str, integer or number] | yes | One numeric value per model input, keyed by feature name (see GET /api/features). Text and booleans are rejected. |

### ValidationIssue

| Field | Type | Required | Description |
|---|---|---|---|
| `row` | integer or null | no | Line number in the file (header = line 1). |
| `column` | string or null | no |  |
| `problem` | string | yes |  |
