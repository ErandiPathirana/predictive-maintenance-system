"""Shared helpers for the full-stack end-to-end tests: start/stop the REAL backend with real environment variables,
read the SQLite database directly (an independent check of what was really saved), and record results for the report.

CLI (used by the browser tests):
    python harness.py serve --bundle <dir> --db <file.db> --port 8000 [--no-model]
    python harness.py dropdb --db <file.db>        (breaks the database under a running server)
"""
import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BACKEND = ROOT / "backend"
OUT = HERE / "out"
CORS = "http://localhost:5173,http://127.0.0.1:5173"


def server_env(bundle: Path, db: Path, *, require_model=True, extra=None) -> dict:
    env = dict(os.environ)
    env.update({"ENVIRONMENT": "test", "MODEL_BUNDLE_DIR": str(bundle), "DATABASE_URL": f"sqlite:///{Path(db).as_posix()}",
                "AUTO_CREATE_TABLES": "true", "CORS_ORIGINS": CORS, "REQUIRE_MODEL_AT_STARTUP": "true" if require_model else "false",
                "LOG_LEVEL": "INFO", "PYTHONUNBUFFERED": "1"})
    env.update(extra or {})
    return env


class Server:
    """The real backend, started the same way a user starts it: python -m uvicorn app.main:app (environment variables only)."""

    def __init__(self, bundle, db, port=8000, *, require_model=True, extra_env=None):
        self.bundle, self.db, self.port = Path(bundle), Path(db), port
        self.require_model, self.extra_env = require_model, extra_env
        self.proc = None; self.log_path = OUT / f"server-{port}.log"

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}"

    def start(self, wait=True, timeout=40):
        OUT.mkdir(parents=True, exist_ok=True)
        self.log = open(self.log_path, "ab")
        self.proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(self.port), "--log-level", "warning"],
                                     cwd=BACKEND, env=server_env(self.bundle, self.db, require_model=self.require_model, extra=self.extra_env),
                                     stdout=self.log, stderr=subprocess.STDOUT)
        if wait:
            t0 = time.time()
            while time.time() - t0 < timeout:
                if self.proc.poll() is not None:
                    return self
                try:
                    urllib.request.urlopen(self.url + "/api/health", timeout=1).read(); return self
                except Exception:
                    time.sleep(0.25)
            raise RuntimeError("server did not answer /api/health in time:\n" + self.log_tail())
        return self

    def exited(self):
        return self.proc is not None and self.proc.poll() is not None

    def log_tail(self, n=1500):
        self.log.flush(); return self.log_path.read_text(errors="replace")[-n:]

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()                        # SIGTERM on Linux/macOS (graceful), TerminateProcess on Windows
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        try:
            self.log.close()
        except Exception:
            pass

    def __enter__(self):
        return self.start()

    def __exit__(self, *a):
        self.stop()


# ----------------------------- independent database access (no application code) -----------------------------
def db_rows(db: Path, where="1=1", args=()):
    con = sqlite3.connect(str(db)); con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute(f"SELECT * FROM predictions WHERE {where} ORDER BY id", args)]
    finally:
        con.close()


def db_count(db: Path, table="predictions"):
    con = sqlite3.connect(str(db))
    try:
        return con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        con.close()


def decode_row(r: dict) -> dict:
    out = dict(r)
    for k in ("scores", "recommendations", "input_readings"):
        if isinstance(out.get(k), str):
            out[k] = json.loads(out[k])
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve"); s.add_argument("--bundle", required=True); s.add_argument("--db", required=True); s.add_argument("--port", type=int, default=8000)
    s.add_argument("--no-model", action="store_true")
    d = sub.add_parser("dropdb"); d.add_argument("--db", required=True)          # simulates a database failure under a running server
    a = ap.parse_args()
    if a.cmd == "dropdb":
        con = sqlite3.connect(a.db); con.execute("DROP TABLE predictions"); con.commit(); con.close(); sys.exit(0)
    env = server_env(Path(a.bundle), Path(a.db), require_model=not a.no_model)
    os.chdir(BACKEND)
    os.execvpe(sys.executable, [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(a.port), "--log-level", "warning"], env)
