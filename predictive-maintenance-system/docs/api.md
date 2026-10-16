# API documentation

Base path: `/api/v1`. Live interactive docs (Swagger UI) are generated automatically at **`/docs`**; the machine-readable spec is at `/openapi.json`.

## Endpoints

### `GET /api/v1/health`
Is the server up, and is a model loaded?
```json
{ "status": "ok", "app_name": "Predictive Maintenance API", "app_version": "0.1.0",
  "environment": "development", "model_ready": false }
```

### `GET /api/v1/model/info`
Always returns 200. If the model is not loaded, `reason` explains why.
```json
{ "model_ready": true,
  "metadata": { "model_name": "...", "model_version": "...", "positive_class": 1, "decision_threshold": null },
  "feature_count": 5 }
```

### `GET /api/v1/model/features`
Lists the inputs the model needs (name, unit, optional min/max). `503` if the model is not ready.

### `POST /api/v1/predict`
Request:
```json
{ "machine_id": "optional label", "readings": { "<feature_name>": 12.3 } }
```
Success (`200`):
```json
{ "machine_id": "optional label", "failure_probability": 0.0, "predicted_failure": false,
  "decision_threshold": null, "model_name": "...", "model_version": "..." }
```
(The numbers above are format examples only, not model output.)

## Error format (all errors)

```json
{ "error": { "code": "machine_readable_code", "message": "Plain English.", "details": { } } }
```

| HTTP | `code` | Meaning |
|---|---|---|
| 422 | `invalid_request` | Body is not valid JSON of the expected shape (e.g. text instead of a number). `details.problems` lists each field. |
| 422 | `invalid_sensor_readings` | Readings are missing, unknown, non-finite or outside the allowed range. `details` lists `missing_features`, `unknown_features`, `non_finite_values`, `out_of_range`. |
| 503 | `model_not_ready` | Model files are missing or failed to load. |
| 500 | `prediction_failed` | The model could not score this input. |
| 500 | `internal_error` | Unexpected server error (details are logged, not returned). |
| 404/405 | `http_error` | Unknown route or wrong method. |

## Try it from PowerShell

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/health
```
