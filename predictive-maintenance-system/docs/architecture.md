# System architecture

## Overview

```
 Viva panel device (browser)
        |  HTTPS
        v
 Frontend (React + TypeScript, static files)         <- hosted on a static host
        |  HTTPS, JSON
        v
 Backend (FastAPI)                                   <- hosted on a web-service host
   routes -> validation -> preprocessing -> prediction
                                   ^
                                   | loaded once at startup
                          Model artifacts (3 files)  <- exported from Google Colab
```

## Components

| Component | Responsibility | Key files |
|---|---|---|
| Frontend | Show system status, collect sensor readings (next stage), display risk and errors clearly. Holds no model and no secrets. | `frontend/src/` |
| API routes | Thin HTTP layer under `/api/v1`. | `backend/app/api/routes.py` |
| Configuration | Reads settings from environment variables. | `backend/app/config.py` |
| Model loader | Loads model, schema and metadata once; reports "not ready" instead of crashing. | `backend/app/services/model_loader.py` |
| Data validation | Rejects missing, unknown, non-finite or out-of-range readings with all problems listed. | `backend/app/services/data_validation.py` |
| Preprocessing | Orders values to match training columns. Scaling/encoding is inside the saved Pipeline. | `backend/app/services/preprocessing.py` |
| Prediction | Computes failure probability and applies the decision threshold. | `backend/app/services/prediction.py` |
| Error handling | One error shape for every failure. | `backend/app/errors.py` |
| ML bridge | Exports and validates model artifacts. | `ml/` |

## Design decisions (and why)

1. **Pipeline-in-a-file.** Preprocessing lives inside the exported scikit-learn Pipeline so serving cannot drift from training.
2. **Schema-driven validation.** Feature names and ranges come from `feature_schema.json`, so changing the model never requires editing validation code.
3. **Start without a model.** The API runs and explains the problem when artifacts are missing. This makes development, testing and deployment debugging far easier.
4. **No hard-coded thresholds.** The decision threshold and valid ranges come from your analysis (metadata/schema), never from the code.
5. **Model files stay out of GitHub.** They may be large or confidential.

## Security notes

- `.env` is never committed; only `.env.example` (placeholders) is.
- `VITE_*` variables are public in the browser; never put secrets there.
- CORS only allows origins listed in `CORS_ORIGINS`.
- `joblib` files can execute code on load: load only files you created.
- Error responses never include stack traces or server file paths.
