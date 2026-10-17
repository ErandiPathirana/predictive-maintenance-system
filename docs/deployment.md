# Deployment instructions

Goal: viva panel members open a web address on their own device. This needs a hosted **frontend** (static files) and a hosted **backend** (Python service).

> I have not verified any hosting provider's current free-tier limits, prices or screens. Provider websites change, so check their current documentation before the viva. Free backend services often "sleep" when idle, so the first request can take up to a minute. **Open the site a few minutes before your viva to wake it up.**

## Stage plan
Deployment files (hosting configuration) are added in a later build stage, once the prediction form exists. This page explains the approach so you can plan.

## Step 1: Put code on GitHub
```powershell
git init
git add .
git status        # CHECK: no .env, no .csv, no .joblib files listed
git commit -m "Initial project structure"
```
Create an empty GitHub repository (preferably **private**), then follow the commands GitHub shows (`git remote add origin ...`, `git push -u origin main`).

## Step 2: Backend host
Any host that runs a Python web service works (Render, Railway, Fly.io, etc.).
- Root directory: `backend`
- Install command: `pip install -r requirements-postgres.txt`
- Release/pre-start command: `python -m alembic upgrade head`
- Start command: `python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Python version: **3.12**
- Environment variables (set on the host, never in Git): `ENVIRONMENT=production`, `CORS_ORIGINS=<your frontend address>` (no `*`),
  `DATABASE_URL=<hosted PostgreSQL URL>`, `MODEL_BUNDLE_DIR=<path to the bundle>`, `API_KEY=<long random string>` (recommended),
  `REQUIRE_MODEL_AT_STARTUP=true`. In production the app refuses `*` CORS, smoke-test bundles and auto-created tables.

## Step 3: Getting the model bundle onto the backend
The bundle is not in GitHub. It contains no pickle and no code that the backend runs, and `MANIFEST.json` lets the server detect a damaged copy. Options:
1. **Small bundle in a private repository:** add `ml/artifacts/pm_condition_ann_v1.0.0/` with `git add -f`. Acceptable only if the model reveals nothing confidential and the repository stays private. Delete `model.keras` and any `__pycache__` first (the backend does not need them).
2. **Persistent disk/volume** (if the host offers one): upload the bundle there and set `MODEL_BUNDLE_DIR` to the mount path.
3. **Private object storage download at build/start:** needs extra deployment code (not built yet).

Run `python ml/scripts/validate_artifacts.py` locally first. On the host, the server logs `Model bundle ... loaded and verified` or stops with the reason.

## Step 4: Frontend host
Any static host works (Vercel, Netlify, Cloudflare Pages, GitHub Pages).
- Root directory: `frontend`
- Build command: `npm run build`
- Output directory: `dist`
- Environment variable: `VITE_API_BASE_URL=<your backend address>` (set it **before** building; it is baked into the build)

## Step 5: Connect them
1. Put the frontend address into the backend's `CORS_ORIGINS` (no trailing slash).
2. Open the frontend. The top-right light should read **Model <version> ready**. The Dashboard and Research information pages show more detail.

## Pre-viva checklist
- [ ] Works on a phone and a laptop that you did not develop on
- [ ] Opened the site 10 minutes before the viva
- [ ] `/docs` on the backend loads and `GET /api/health` shows `"status": "ok"`
- [ ] `API_KEY` is set if real data is used
- [ ] A local copy runs too (backup if the internet fails). Keep screenshots as a last resort.
- [ ] No secrets in the repository (`git log` and GitHub search for `.env`)
