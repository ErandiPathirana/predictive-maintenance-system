"""One command for the whole end-to-end suite (Windows, macOS, Linux).  Run from the repository root:
    python tests/e2e_full/run_all.py            (add --skip-browser to run only the API/database layer)
Steps: pytest API+DB+rules -> build the frontend for http://localhost:8000 -> serve it on :5173 -> Playwright browser layer -> report.
Needs: backend requirements installed, `npm install` in frontend and in tests/e2e, `npx playwright install chromium` in tests/e2e."""
import os, shutil, subprocess, sys, time, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent; ROOT = HERE.parent.parent
PY = sys.executable; NPM = shutil.which("npm") or "npm"; NPX = shutil.which("npx") or "npx"; NODE = shutil.which("node") or "node"
env = {**os.environ, "PM_PYTHON": PY}
def run(cmd, cwd, **kw):
    print("\n$", " ".join(map(str, cmd)), f"   (in {cwd})"); return subprocess.run(cmd, cwd=cwd, env={**env, **kw.pop("env", {})}, **kw).returncode

rc = run([PY, "-m", "pytest", "-p", "plugin_e2e", "-q", "test_e2e_api_db.py", "test_recommendation_rules.py"], HERE)
if "--skip-browser" not in sys.argv:
    rc |= run([NPM, "run", "build"], ROOT / "frontend", env={"VITE_API_BASE_URL": "http://localhost:8000"})
    prev = subprocess.Popen([NPX, "vite", "preview", "--port", "5173", "--strictPort"], cwd=ROOT / "frontend", env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=(os.name == "nt"))
    try:
        for _ in range(60):
            try: urllib.request.urlopen("http://localhost:5173", timeout=2); break
            except Exception: time.sleep(0.5)
        rc |= run([NODE, "suite_full.mjs"], ROOT / "tests" / "e2e")
    finally:
        if os.name == "nt": subprocess.run(["taskkill", "/F", "/T", "/PID", str(prev.pid)], capture_output=True)
        else: prev.terminate()
run([PY, "report.py"], HERE)
print("\nReport: docs/e2e-test-report.md   (exit code != 0 means a test FAILED; BLOCKED and KNOWN GAP do not fail the run)"); sys.exit(1 if rc else 0)
