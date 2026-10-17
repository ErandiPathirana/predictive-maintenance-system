# Frontend guide

React 19 + TypeScript + Vite, Mantine 9 (components), Recharts (charts), PapaParse (reading CSV in the browser), React Router (hash routes).
The frontend is a **separate service**: it only talks to the backend through `frontend/src/api/client.ts`.

## Pages
| Page | Route | Data source |
|---|---|---|
| Dashboard | `#/` | `GET /api/predictions` (newest 5,000 stored predictions, summarised in the browser) + the file loaded in this session |
| Motor monitoring | `#/monitoring` | The CSV loaded on the Upload page (kept in memory only) |
| Upload and analyse | `#/upload` | `GET /api/template.csv`, `POST /api/uploads/validate`, `POST /api/predict/batch`, `GET /api/reports/predictions.csv` |
| Prediction results | `#/results` | Response of the last `POST /api/predict/batch` in this tab |
| Prediction history | `#/history` | `GET /api/predictions`, `GET /api/reports/predictions.csv` |

Only endpoints that exist in the backend are used. Because the backend has no summary endpoint and does not store sensor readings by default:
- Dashboard counts are computed in the browser from the newest stored predictions (a notice appears if there are more than it loaded).
- "Latest condition per motor" uses the **measurement time** (`measured_at`). A motor with no measurement times falls back to the time the prediction was stored, and the page marks that row with `*`.
- Sensor trend charts exist only for the CSV you load in the current browser tab.

## Install and run (PowerShell)
```powershell
cd C:\path\to\predictive-maintenance-system\frontend
npm install
copy ..\.env.example ..\.env      # skip if .env already exists; VITE_API_BASE_URL is read from the project-root .env
npm run dev                       # http://localhost:5173  (backend must be running on the address in VITE_API_BASE_URL)
```
Checks:
```powershell
npm run typecheck
npm test                          # 45 tests
npm run build                     # writes frontend\dist
npm run preview                   # serve the built site, http://localhost:4173
```
Add `http://localhost:5173` (and `http://localhost:4173` for preview) to `CORS_ORIGINS` in `.env`, then restart the backend.

## Configuration
| Variable | Meaning |
|---|---|
| `VITE_API_BASE_URL` | Backend address, e.g. `https://your-api.example.org`. Baked into the build, so set it **before** `npm run build`. In `npm run dev` it falls back to `http://localhost:8000`; a production build without it shows a clear "not configured" message and never calls localhost. |

Only `VITE_` variables reach the browser. Never put secrets in them. No model files, database URLs or keys are in the frontend.

### Optional access key
If the backend has `API_KEY` set, choose **Access key** at the top of the page and type it. It is sent as the `X-API-Key` header and kept **in memory only** (forgotten on reload). A key typed into a public website is not a strong secret. It only keeps casual visitors out. For real plant data use proper authentication.

## Model evaluation report
The page shows numbers from the training notebook's one-time test run, copied without change. Create the file after training:
```powershell
python ml\scripts\export_evaluation_report.py ml\artifacts\pm_condition_ann_v1.0.0 --data-origin real
```
It writes `frontend\public\evaluation_report.json`. Rebuild (or restart `npm run dev`) afterwards.
- `--data-origin` must be `real` or `synthetic`. The bundle does not record this, so you say it. Default is `unknown`, and the page then warns.
- The exporter refuses smoke-test bundles and bundles without a confusion matrix.
- Until the file exists the page shows no numbers at all. Nothing is a placeholder.
- Do **not** commit a report made from private data if the repository is public.

## Privacy
- Uploaded CSV data is parsed in the browser and held in React state only. It is never written to `localStorage`, `sessionStorage` or cookies. Reloading the page clears it.
- The CSV is sent to the backend only when you press **Check file** or **Analyse file**.
- Removing a file asks for confirmation.

## Accessibility and design choices
Skip link, landmarks, keyboard-reachable tables and filters, visible focus, status shown as **shape + word + colour** (never colour alone), light theme only, no decorative animation (and none at all when the system asks for reduced motion). Charts use four fixed series colours (blue, orange, aqua, yellow) plus different line patterns, a show/hide checkbox legend, hover values, and a **Show as table** switch for every chart.

## Tests
`src/**/*.test.ts(x)` (Vitest + Testing Library). `src/test/fixtures/*.json` are real backend responses captured by `backend/scripts/export_api_fixtures.py` from a **random-weight test model**. They are test data, not research results. `src/types/fixtures.test.ts` assigns them to the TypeScript interfaces, so `npm run typecheck` fails if the backend schema and frontend types drift apart. To refresh them: `python backend\scripts\export_api_fixtures.py`.

## Known limits
- Light theme only; no dark mode yet.
- Charts show every reading. Files near the 5,000-row limit draw without markers and are fine, but are not downsampled.
- The dashboard summarises at most the newest 5,000 stored predictions.
- A file with an empty sensor cell can be charted (gaps are shown) but the backend refuses to analyse it, by design.

## New motor assessment (Prompt 10, Stage 3)

- **Page:** `#/assess`. The form is built from `GET /api/features`, so field names, units and order always match the loaded model. Inputs are grouped by bearing position (drive end / non-drive end, horizontal / vertical) plus operating conditions (rotational speed, load).
- **Validation (before anything is sent):** every reading must be a plain number. Empty, text, NaN, infinity and "1,5" are refused and are never replaced with zero. Timestamps must be real dates. Entries are kept when validation fails. Values outside the training range give a soft warning only (not an alarm limit).
- **Submitting:** one request at a time. Each form session has an `Idempotency-Key`; it is reused only for an identical payload, so a repeat click or retry cannot create a second record. "Saved" is shown only when the server says `saved: true`.
- **Result:** predicted condition (shape + word + colour), prioritised next steps with timing, role and source, return-to-service questions, a Danger notice, model scores labelled as not calibrated, and print / CSV download.
- **History:** each row links to `#/assessment/<id>`, which reopens the stored result and recommendations.
- Fixtures `assessment*.json` and `motors.json` are real backend responses (`backend/scripts/export_api_fixtures.py`).

> The Model evaluation and Research information pages were removed from the website. The evaluation export script (`ml/scripts/export_evaluation_report.py`) still works and can feed a report or the written thesis.
