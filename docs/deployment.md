# Deployment guide (public URL)

Goal: the supervisor and viva panel open one web address on their own device.

## Architecture (inspected from the code)
| Part | Technology | Where it runs |
|---|---|---|
| Frontend | React + TypeScript + Vite, hash routes (`#/...`) | Static host (Vercel recommended) |
| Backend | FastAPI (Python 3.12), NumPy-only inference | Render Free web service |
| Model | Exported bundle `ml/artifacts/pm_condition_ann_v1.0.0/` (NumPy weights, no pickle). Loaded once at startup, never trained | Inside the backend repository (private) |
| Database | SQLAlchemy: SQLite file (default) or PostgreSQL via `DATABASE_URL` | See "Data persistence" |

The frontend calls the backend address baked in at build time (`VITE_API_BASE_URL`). Hash routes mean page refresh and direct links work on any static host without rewrite rules.

## Costs and limits (checked in the providers' documentation on 2026-10-19; verify again before the viva)
**Render Free web service** ([docs](https://render.com/docs/free))
- Spins down after 15 minutes without traffic; waking takes about one minute. **Open the site 5 minutes before the viva.**
- 750 free instance hours per month; if used up, free services are suspended until next month.
- The filesystem is **ephemeral**: files (including a SQLite database) are lost on redeploy, restart or spin-down. No persistent disk on the free plan.
- Free Render PostgreSQL: 1 GB, **expires 30 days after creation** (14-day grace), one per workspace, no backups.

**Vercel Hobby (free)** ([docs](https://vercel.com/docs/plans/hobby)): free for personal, non-commercial use, which fits an academic demonstration. Check that "Vercel Authentication" is not forcing visitors to log in (test in a private window).

Other limits in this app: upload limit 2,000,000 bytes and 5,000 rows per CSV (`MAX_UPLOAD_BYTES`, `MAX_BATCH_ROWS`).

## Data persistence
- Default `DATABASE_URL=sqlite:///predictions.db`: history is kept across normal requests but **is erased whenever Render restarts, redeploys or spins the service down**. Acceptable for a demonstration if you upload a CSV before showing the dashboard.
- To keep history for the viva: create a Render PostgreSQL database (free, valid 30 days, so create it close to the viva) and set `DATABASE_URL` to its **Internal Database URL**. The code converts `postgres://` URLs and `psycopg` is already in `backend/requirements-postgres.txt`.
- `STORE_INPUT_READINGS=false` (default): raw sensor values are not written to the database.

## Environment variables (backend)
| Variable | Value | Secret? |
|---|---|---|
| `ENVIRONMENT` | `production` | no |
| `CORS_ORIGINS` | your frontend address, e.g. `https://your-app.vercel.app` (no trailing slash, **no `*`**) | no |
| `MODEL_BUNDLE_DIR` | `ml/artifacts/pm_condition_ann_v1.0.0` | no |
| `REQUIRE_MODEL_AT_STARTUP` | `true` | no |
| `DATABASE_URL` | `sqlite:///predictions.db` or the PostgreSQL URL | **yes if PostgreSQL** |
| `API_KEY` | optional long random string. If set, viewers must type it into the "Key (access)" button | **yes** |
| `STORE_INPUT_READINGS` | `false` | no |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_SECURITY`, `SMTP_USERNAME`, `SMTP_FROM` | optional, only to e-mail reports (see `docs/maintenance_workflow.md`) | no |
| `SMTP_PASSWORD` | the mail account's password or app password | **yes** |
| `EMAIL_ALLOWED_DOMAINS` | e.g. `your-company.example`; required (or `API_KEY`) when e-mail is on in production | no |
| `PUBLIC_APP_URL` | optional: your frontend address, adds a link in the e-mail | no |

Frontend (set in the static host before building): `VITE_API_BASE_URL` = the backend address (no trailing slash). Never put secrets in a `VITE_` variable: it is visible in the browser.

Files already prepared: `render.yaml` (backend blueprint) and `.python-version` (`3.12`, because Render's newer default Python may not have builds for the pinned packages).

## Step 1: Put the code on GitHub (private repository)
1. Run `python ml/scripts/validate_artifacts.py` locally and confirm the bundle is valid.
2. Delete only `__pycache__` folders from the bundle folder. **Do not delete any file listed in `MANIFEST.json`** (including `model.keras`): the backend refuses to start if a listed file is missing, even though it never loads `model.keras`. If you really want to leave `model.keras` out, also remove its line from `MANIFEST.json`, then run `python ml/scripts/validate_artifacts.py`. Note that `.gitignore` ignores `*.keras`, so a `model.keras` that stays in the bundle must be added with `git add -f`.
3. In PowerShell, from the project folder:
   ```powershell
   git init
   git add .
   git add -f ml/artifacts/pm_condition_ann_v1.0.0     # the bundle is ignored by default, so force it in
   git status                                         # CHECK: no .env, no .csv data, no .db, no .keras
   git commit -m "Prepare deployment"
   ```
4. On github.com choose **New repository**, name it, select **Private**, create it, then run the two commands GitHub shows (`git remote add origin ...` and `git push -u origin main`).
   Only do this if the model reveals nothing confidential.

## Step 2: Deploy the backend on Render
1. Open https://render.com and sign in with GitHub.
2. Choose **New > Web Service** and connect your private repository (branch `main`).
3. Settings: Language **Python 3**, Region nearest to you, Instance type **Free**, Root Directory **leave empty**.
   - Build Command: `pip install -r backend/requirements-postgres.txt`
   - Start Command: `cd backend && python -m alembic upgrade head && python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Health Check Path: `/api/health`
   (Alternatively choose **New > Blueprint** to read these from `render.yaml`.)
4. Under **Environment**, add the variables in the table above. For now set `CORS_ORIGINS` to `https://placeholder.invalid`; you will correct it in Step 4.
5. Click **Create Web Service**. Open the **Logs** tab and wait for `Model bundle ... loaded and verified`, then `Application startup complete`.
6. Copy the service address (like `https://pm-backend-xxxx.onrender.com`). Open `<address>/api/health`: it must show `"model_ready": true` and `"database": "ok"`. `<address>/docs` shows the API documentation.

## Step 3: Deploy the frontend on Vercel
1. Open https://vercel.com, sign in with GitHub, choose **Add New > Project**, import the same repository.
2. **Root Directory: `frontend`**. Framework preset: **Vite**. Build Command `npm run build`. Output Directory `dist`.
3. Under **Environment Variables** add `VITE_API_BASE_URL` = your Render address from Step 2.
4. Click **Deploy**. Copy the address (like `https://your-app.vercel.app`).

## Step 4: Connect them
1. In Render > your service > **Environment**, set `CORS_ORIGINS` to the Vercel address exactly (no trailing slash). Save; the service restarts.
2. Open the Vercel address. The top-right light must read **Model ... ready**.
3. If you change `VITE_API_BASE_URL` later, **redeploy** the frontend (it is baked into the build).

## Reading logs and fixing errors
| Symptom | Likely cause and fix |
|---|---|
| Build fails installing numpy/pydantic | Python version too new. Confirm `.python-version` (`3.12`) is in the repo root |
| `STARTUP ABORTED: database tables are missing` | The start command did not run `alembic upgrade head`; copy the full command above |
| `STARTUP ABORTED` and a model message | Bundle missing or damaged in the repository: re-run Step 1 (`git add -f`), check `MODEL_BUNDLE_DIR` |
| Browser shows "backend unreachable" | Backend asleep (wait about a minute and reload), wrong `VITE_API_BASE_URL`, or `CORS_ORIGINS` not equal to the frontend address |
| Browser console shows a CORS error | `CORS_ORIGINS` has a typo, a trailing slash or `http` instead of `https` |
| Every request says access key needed | `API_KEY` is set; click **Key (access)** and type it, or remove the variable |

## Security notes
- `.env`, datasets, databases and trained files are ignored by `.gitignore`; keep the repository private and use no real company data.
- Without `API_KEY`, anyone with the address can use the API and see stored predictions. Use only demo data, or set `API_KEY` and share it with the panel. The key is typed into a browser, so it is not strong secrecy.
- The access key is held in memory only, and the production settings refuse `*` for CORS.

## Pre-viva checklist
- [ ] `<backend>/api/health` shows `model_ready: true`
- [ ] Opened the site 5 minutes before the viva (wakes the backend)
- [ ] Six menu items work; download the CSV template on the Upload page, fill it with safe test values, upload it and see results; invalid CSV shows a clear message
- [ ] Tested on a phone and on a device you did not develop on, in a private window
- [ ] A local copy runs too (backup if the internet fails) and screenshots are saved
