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

### InputWarning

| Field | Type | Required | Description |
|---|---|---|---|
| `feature` | string | yes |  |
| `value` | number | yes |  |
| `observed_train_min` | number or null | yes |  |
| `observed_train_max` | number or null | yes |  |
| `message` | string | yes |  |

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
