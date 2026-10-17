# Predictive Maintenance System

**A Machine Learning Approach to Proactive Machine Failure Prediction for Modern Manufacturing Systems**
Final-year Computer Science research artefact (prototype).

> The model predicts a **recorded condition class** (Normal / Alert / Danger). That is **not** a confirmed machine failure,
> the scores are **not calibrated probabilities**, and results are flagged *demonstration only* until the label provenance is documented.

## What is built
| Part | Status |
|---|---|
| FastAPI backend: artifact loading with startup validation, strict CSV and JSON validation, single + batch prediction, SQLAlchemy history (SQLite/PostgreSQL), Alembic migrations, filtered history, CSV export, Swagger docs | Done, 131 tests |
| Colab notebook (`ml/notebooks/`) producing the versioned artifact bundle | Done (tested on synthetic data only) |
| React status page (server, database, model, demonstration banner) | Done, 11 tests |
| Prediction form, CSV upload and history screens in the frontend | **Next stage** |
| Dataset cleaning module, data dictionary, data-quality report | Pending your answers to the open questions |

## Folders
| Folder | Purpose |
|---|---|
| `backend/` | FastAPI app (`app/`), Alembic migrations (`migrations/`), requirements, `scripts/generate_api_docs.py` |
| `frontend/` | React + TypeScript (Vite) |
| `ml/` | Training notebook, bundle validator, git-ignored `artifacts/` |
| `docs/` | API, schemas, artifact contract, database, architecture, deployment, testing, evaluation, dataset, model card |
| `tests/backend/` | pytest unit and integration tests |

## Setup on Windows (PowerShell)
Use **Python 3.12** (3.14 has no ready-made numpy builds for these pins). If `python --version` shows another version, create the environment with the full path to 3.12, e.g.
`& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" -m venv .venv`.

```powershell
cd C:\path\to\predictive-maintenance-system
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python --version                                  # must print 3.12.x
python -m pip install --upgrade pip
pip install -r backend\requirements-dev.txt
```

### 1. Put the trained bundle in place
Unzip the notebook's `pm_condition_ann_v1.0.0.zip` into `ml\artifacts\` (see `ml/README.md`), then check it:
```powershell
python ml\scripts\validate_artifacts.py
```
`OK: ...` means the backend can load it. If `.env` says `MODEL_BUNDLE_DIR=ml/artifacts/pm_condition_ann_v1.0.0`, the folder name must match.

### 2. Create the database tables (once)
```powershell
cd backend
python -m alembic upgrade head
```

### 3. Test, then run
```powershell
python -m pytest                                  # expect: 131 passed, 1 skipped
python -m uvicorn app.main:app --reload
```
Open <http://localhost:8000/docs> (Swagger UI). Step-by-step Swagger testing is in `docs/api.md`.
If the bundle is missing or invalid, the server **refuses to start** and prints the reason. That is intentional.

### 4. Frontend (second PowerShell window)
```powershell
cd C:\path\to\predictive-maintenance-system\frontend
npm install
npm test                                          # expect: 11 passed
npm run dev                                       # http://localhost:5173
```

## Developing before you have a real bundle
You can set `ALLOW_SMOKE_TEST_BUNDLE=true` to load a notebook bundle made with `FAST_DEBUG`. Results from such a bundle are invalid. Never use that setting in production (the app refuses it there).

## Troubleshooting
| Symptom | Fix |
|---|---|
| `STARTUP ABORTED: Model bundle folder not found` | Unzip the bundle into `ml\artifacts\` and check `MODEL_BUNDLE_DIR` in `.env` |
| `STARTUP ABORTED: ... Checksum mismatch` | A bundle file was edited or the zip is corrupt. Export it again |
| `STARTUP ABORTED: database tables are missing` | Run `python -m alembic upgrade head` in `backend` |
| CORS error in the browser | Add the frontend address to `CORS_ORIGINS` in `.env` and restart the backend |
| CSV rejected | Read `details.issues` in the 422 response. Row, column and reason are listed |
| `pip install` tries to compile numpy | Wrong Python version. Recreate the venv with Python 3.12 |
