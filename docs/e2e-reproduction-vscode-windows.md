# Reproducing the end-to-end tests in VS Code on Windows

Open the repository folder in VS Code, then **Terminal → New Terminal** (PowerShell). Every command is run from the repository root unless stated.

## 0. One-time setup
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # if blocked: Set-ExecutionPolicy -Scope Process Bypass
pip install -r backend\requirements.txt pytest httpx
cd frontend;  npm install;  cd ..
cd tests\e2e; npm install; npx playwright install chromium; cd ..\..
```
The synthetic model is trained with NumPy only (no TensorFlow needed).

## 1. Everything in one command
```powershell
python tests\e2e_full\run_all.py            # add --skip-browser for the API/database layer only
```
It runs pytest, builds the frontend for `http://localhost:8000`, serves it on port 5173, runs the Playwright browser tests, and writes `docs\e2e-test-report.md`. Ports 8000, 8101, 5173 and 8110–8189 must be free. Exit code 0 = no FAIL (BLOCKED and KNOWN GAP do not fail the run).

## 2. Step by step (to reproduce a single scenario)
| What | Command |
|---|---|
| A–L API + database, all | `cd tests\e2e_full; python -m pytest` |
| One scenario | `python -m pytest test_e2e_api_db.py -k test_E_invalid` (names: `test_A_normal`, `test_B_alert`, `test_C_danger`, `test_D_missing`, `test_E_invalid`, `test_F_csv_columns`, `test_CSV_valid`, `test_G1…G3`, `test_H1`, `test_H2`, `test_I…`, `test_J…`, `test_K…`, `test_L_export`) |
| Recommendation rules / test double | `python -m pytest test_recommendation_rules.py` |
| Browser layer | `cd frontend; $env:VITE_API_BASE_URL="http://localhost:8000"; npm run build; npx vite preview --port 5173` (leave running) then in a second terminal `cd tests\e2e; $env:PM_PYTHON="..\..\.venv\Scripts\python.exe"; node suite_full.mjs` |
| Report | `python tests\e2e_full\report.py` |

Look at the database yourself: `python tests\e2e_full\db_query.py tests\e2e_full\out\e2e_main.db "1=1"` prints every stored row. Screenshots are in `tests\e2e\evidence\FULL-*.png`; server logs in `tests\e2e_full\out\server-*.log`.

## 3. Using your REAL model (turns the BLOCKED tests into real results)
1. Export the bundle from Colab into `ml\artifacts\<bundle-name>\` (never commit confidential data).
2. `$env:PM_REAL_BUNDLE_DIR="C:\...\ml\artifacts\<bundle-name>"`
3. Optional: a CSV of real labelled rows in the upload template format plus `condition_label`: `$env:PM_REAL_SAMPLES_CSV="C:\...\real_rows.csv"`
4. `cd tests\e2e_full; python -m pytest test_recommendation_rules.py -k "B1 or B2"`
The test reports which classes the real model really produces; it never forces a class.

## 4. Failure scenarios, what they do
G1–G3 start extra servers with a missing or damaged copy of the bundle; H1 drops the `predictions` table under a running server; H2 points to an unwritable database path. They only touch files under `tests\e2e_full\out`.
