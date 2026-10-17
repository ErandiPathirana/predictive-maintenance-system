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
| GET | `/api/predictions` | Prediction history (newest first), filter by motor, batch, class or date |
| GET | `/api/predictions/{prediction_id}` | One stored prediction |
| GET | `/api/batches` | Recent CSV upload batches |
| GET | `/api/reports/predictions.csv` | Export prediction results to CSV (same filters as the history) |

## Schemas

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
