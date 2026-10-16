# Predictive Maintenance System

**A Machine Learning Approach to Proactive Machine Failure Prediction for Modern Manufacturing Systems**
Final-year Computer Science research artefact (prototype).

Predictions are decision support for a research prototype, not a safety system.

## What is built so far (Stage 1: project foundation)

- FastAPI backend with validation, structured errors, auto-generated docs, and a model loader that starts safely **even before a model exists**
- React + TypeScript frontend with a responsive System status page
- Colab-to-backend bridge (`ml/`) with an export helper and a local validator
- Automated tests: 26 backend, 10 frontend
- Documentation templates in `docs/`

**Not built yet:** the prediction form and results screen (Stage 2), model integration with your real data (Stage 3), deployment files (later). No dataset, model or result is included, and none has been invented.

## Folder guide

| Folder / file | Purpose |
|---|---|
| `frontend/` | The website users see (React + TypeScript + Vite) |
| `backend/` | The API server (FastAPI). `app/services/` holds the logic, `app/api/` the endpoints |
| `ml/` | Colab notebook template, export helper, and the (git-ignored) `artifacts/` folder for your trained model |
| `docs/` | Architecture, dataset, API, model card, deployment, testing and evaluation documents |
| `tests/` | Backend tests (pytest) and a guide to the frontend tests |
| `.gitignore` | Stops secrets, datasets, model files, caches and logs from reaching GitHub |
| `.env.example` | Settings template with placeholders. Copy to `.env` (never commit `.env`) |

## Setup on Windows (PowerShell)

### 0. Check your tools
```powershell
python --version    # use Python 3.11 or 3.12 (3.10+ required)
node --version      # Node.js 20 or newer
git --version
```
Missing something? Install Python from python.org (tick "Add to PATH"), Node.js LTS from nodejs.org, Git from git-scm.com.

### 1. Get the project
If you received it as a zip, extract it, then:
```powershell
cd C:\path\to\predictive-maintenance-system
code .              # opens Visual Studio Code here
```
(To recreate the empty folder skeleton by hand instead: `mkdir frontend, backend, ml, docs, tests`.)

### 2. Create your settings file
```powershell
Copy-Item .env.example .env
```

### 3. Backend: install
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```
If PowerShell says scripts are disabled, run this once, then activate again:
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```
Then:
```powershell
python -m pip install --upgrade pip
pip install -r backend\requirements-dev.txt
```

### 4. Backend: test and run
```powershell
cd backend
python -m pytest                                  # expect: 26 passed
python -m uvicorn app.main:app --reload           # leave this window open
```
Open <http://localhost:8000/docs> (API docs) and <http://localhost:8000/api/v1/health>.
Without a model you will see `"model_ready": false`. That is correct at this stage.

### 5. Frontend: install, test, run (open a SECOND PowerShell window)
```powershell
cd C:\path\to\predictive-maintenance-system\frontend
npm install
npm test                                          # expect: 10 passed
npm run dev
```
Open <http://localhost:5173>. You should see Server **Running** and Trained model **Not loaded**.

### 6. Put the project on GitHub
```powershell
cd C:\path\to\predictive-maintenance-system
git init
git add .
git status          # check that no .env, .csv or .joblib file is listed
git commit -m "Stage 1: project foundation"
```

## Connecting your Colab model (Stage 3 preview)
Read `ml/README.md`. In short: train in Colab, export 3 files, unzip them into `ml\artifacts\`, run `python ml/scripts/validate_artifacts.py`, restart the backend.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `pip install` fails building numpy/pandas | Use Python 3.11 or 3.12; very new Python versions may lack ready-made packages |
| Frontend says "Cannot reach the prediction server" | Backend is not running, or `VITE_API_BASE_URL` in `.env` is wrong. Restart `npm run dev` after editing `.env` |
| Browser console shows a CORS error | Add the frontend address to `CORS_ORIGINS` in `.env`, restart the backend |
| Model fails to load after export | scikit-learn version differs from Colab. See `ml/README.md` |
