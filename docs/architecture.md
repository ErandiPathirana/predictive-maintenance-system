# System architecture

```
 Browser (viva panel)  --HTTPS-->  React frontend (static files)  --HTTPS, JSON-->  FastAPI backend
                                                                                      |  routes -> validation -> inference
 Google Colab (training) --> artifact bundle (folder) --loaded once at startup------>|
                                                                                      |  SQLAlchemy --> SQLite (local) / PostgreSQL (hosted)
```

| Component | Responsibility | Where |
|---|---|---|
| Configuration | Environment variables only; production refuses unsafe settings (`*` CORS, smoke-test bundles, auto-created tables) | `backend/app/core/config.py` |
| Artifact loader | Verifies checksums, contract, shapes, parity probes; refuses to start otherwise | `backend/app/services/artifacts.py` |
| Inference | NumPy forward pass using the training scaler and weights (no TensorFlow, no pickle) | `backend/app/services/inference.py` |
| CSV handling | File checks, strict cell validation, all problems reported, all-or-nothing | `backend/app/services/csv_io.py` |
| Prediction service | Builds structured results, demonstration flag, non-blocking out-of-training-range warnings | `backend/app/services/predictions.py` |
| Database | `upload_batches`, `predictions`; repository functions; Alembic migrations | `backend/app/db/`, `backend/migrations/` |
| Routes | System, prediction, history/report endpoints | `backend/app/api/` |
| Errors and logging | One error shape; no stack traces to users; logs contain no readings, IDs or query strings | `core/errors.py`, `core/logging_utils.py`, `main.py` |

## Design decisions
1. **The model is the bundle.** The backend has no training code and does not change the model. Integrity is checked by SHA-256 and by parity probes computed in the notebook.
2. **Fail fast.** A missing or inconsistent bundle stops startup with a clear message instead of serving wrong predictions. (`REQUIRE_MODEL_AT_STARTUP=false` allows a degraded mode for hosting diagnostics: predictions return 503.)
3. **No invented limits.** Inputs must be finite numbers; there are no alarm thresholds. Values outside the *training* range only produce a warning.
4. **Honest labelling.** Every result carries the model version, provenance flag, demonstration flag and a note that a predicted condition is not a confirmed failure.
5. **Privacy by default.** Sensor values are not stored or logged.

## Security notes
CORS is an explicit list; uploads are limited by type, size, rows and columns and are only parsed as text; filenames are sanitised; CSV exports neutralise spreadsheet formulas; optional `X-API-Key`; secrets live in environment variables.
**Not implemented:** user accounts, rate limiting, deletion of history. The history endpoints are open unless `API_KEY` is set. Before putting real data on a public host, set `API_KEY` and consider a reverse proxy or host-level rate limiting.
