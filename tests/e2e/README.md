# Browser (end-to-end) tests

These tests drive a real Chromium browser against the **real** frontend build and the **real** FastAPI backend.
The backend runs on a small test model whose weights are made up, so it always predicts the class you ask for
(`Normal`, `Alert` or `Danger`). They test the **software**, never the quality of the trained model.

## One-time setup (Windows PowerShell)

```powershell
cd tests\e2e
npm install
npx playwright install chromium        # downloads the browser (about 150 MB)
```

## Run

1. Start the frontend build on port 5173 (it must be built with the API address of the test backend):
   ```powershell
   cd frontend
   $env:VITE_API_BASE_URL = "http://localhost:8000"
   npm run build
   npx vite preview --port 5173 --strictPort      # leave this window open
   ```
2. In a second window run one scenario (the script starts and stops its own backend where needed):
   ```powershell
   cd tests\e2e
   $env:PM_PYTHON = "..\..\backend\.venv\Scripts\python.exe"
   node run_scenario.mjs Danger        # also: Normal, Alert, NoModel, Slow, Outage
   ```
   On Linux/macOS `./run_all.sh` runs every scenario in turn.

Screenshots are written to `tests/e2e/evidence/`, results to `results-<scenario>.json`, axe-core findings to `axe-results.json`.

| Scenario | Backend used | What it covers |
|---|---|---|
| Normal / Alert / Danger | forced-class test model | result page, guidance wording, safety limits, accessibility of the result |
| Danger (extra) | same | form, validation, keyboard, CSV upload, history, export, trends, layouts, accessibility |
| NoModel | server up, no model | "model unavailable" screens |
| Slow | 3 s delay on every call | loading states, double-click protection, 20 s time-out |
| Outage | none (starts and stops one itself) | server off, server dies mid-submit, recovery |

Environment variables: `PM_FRONTEND_URL`, `PM_API_URL`, `PM_PYTHON`, `PM_CHROMIUM` (path to a Chromium to use instead of the Playwright one).
