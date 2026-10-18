#!/usr/bin/env bash
# Runs every scenario. Needs: frontend built with VITE_API_BASE_URL=http://localhost:8000 and served on :5173 (vite preview),
# PM_PYTHON = a python that has the backend requirements installed.
set -u
cd "$(dirname "$0")"
PY="${PM_PYTHON:-python}"
for sc in Normal Alert Danger NoModel Slow; do
  cond=$sc; delay=0
  [ $sc = NoModel ] && cond=none
  [ $sc = Slow ] && { cond=Danger; delay=3; }
  $PY start_backend.py $cond --port 8000 --delay $delay > backend-$sc.log 2>&1 &
  BE=$!
  for i in $(seq 1 60); do curl -s localhost:8000/api/health >/dev/null && break; sleep 0.5; done
  node run_scenario.mjs $sc
  kill $BE 2>/dev/null; wait $BE 2>/dev/null
done
node run_scenario.mjs Outage   # no backend running: this scenario starts and stops its own
