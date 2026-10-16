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
- Install command: `pip install -r requirements.txt`
- Start command: `python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Environment variables: copy from `.env.example`. Set `ENVIRONMENT=production` and `CORS_ORIGINS=<your frontend address>`.
- Python version: use the same minor version you tested with.

## Step 3: Getting the model onto the backend (the hard part)
The 3 artifact files are not in GitHub. Choose one approach:
1. **Small model, private repo:** temporarily allow-list the files and commit them to a **private** repository. Simple, but only acceptable if the model contains no confidential information and the repository stays private. Remove the exception afterwards if needed.
2. **Host persistent disk/volume** (if your host offers one): upload the files there and set `MODEL_DIR` to that mount path.
3. **Private object storage** (download at startup): needs extra code, planned for a later stage if you choose this.

Whichever you pick, run `python ml/scripts/validate_artifacts.py` locally first, and match the scikit-learn version to Colab.

## Step 4: Frontend host
Any static host works (Vercel, Netlify, Cloudflare Pages, GitHub Pages).
- Root directory: `frontend`
- Build command: `npm run build`
- Output directory: `dist`
- Environment variable: `VITE_API_BASE_URL=<your backend address>` (set it **before** building; it is baked into the build)

## Step 5: Connect them
1. Put the frontend address into the backend's `CORS_ORIGINS` (no trailing slash).
2. Open the frontend. The System status page should show Server **Running** and Trained model **Ready**.

## Pre-viva checklist
- [ ] Works on a phone and a laptop that you did not develop on
- [ ] Opened the site 10 minutes before the viva
- [ ] `/docs` on the backend loads
- [ ] A local copy runs too (backup if the internet fails). Keep screenshots as a last resort.
- [ ] No secrets in the repository (`git log` and GitHub search for `.env`)
