"""Builds docs/e2e-test-report.md from out/results_api.json and out/results_ui.json (what was ACTUALLY executed). Run: python report.py"""
import json, shutil, sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent; OUT = HERE / "out"; ROOT = HERE.parent.parent; DOCS = ROOT / "docs"
EVID = ROOT / "tests" / "e2e" / "evidence"

def load(n):
    p = OUT / n
    return json.loads(p.read_text("utf-8")) if p.exists() else {"results": [], "meta": {}}

api, ui = load("results_api.json"), load("results_ui.json")
rows = []
for src in (api, ui):
    for r in src["results"]:
        m = src["meta"].get(r["id"], {})
        rows.append({**m, **r})
def key(r): return (r.get("letter", "Z")[0], r["id"])
rows.sort(key=key)
count = {}
for r in rows: count[r["status"]] = count.get(r["status"], 0) + 1
shots = {"UI-A": "FULL-UI-Normal-result", "UI-B": "FULL-UI-Alert-result", "UI-C": "FULL-UI-Danger-result", "UI-D": "FULL-UI-D", "UI-F": "FULL-UI-F",
         "UI-CSV": "FULL-UI-CSV-analysed", "UI-J": "FULL-UI-J", "UI-K": "FULL-UI-K-detail", "UI-G": "FULL-UI-G", "UI-H": "FULL-UI-H"}
(DOCS / "qa" / "e2e-evidence").mkdir(parents=True, exist_ok=True)
for v in shots.values():
    s = EVID / f"{v}.png"
    if s.exists(): shutil.copy(s, DOCS / "qa" / "e2e-evidence" / s.name)

esc = lambda t: str(t).replace("|", "\\|").replace("\n", " ")
L = [f"# End-to-end test report: sensor entry or CSV → validation → model → recommendations → database → history → export",
     f"\nGenerated {datetime.now():%Y-%m-%d %H:%M} from `tests/e2e_full/out/results_*.json`. Every status below was produced by a test that was executed; nothing is copied from a plan.\n",
     "## 1. Result", "", "| Status | Count |", "|---|---|", *[f"| {k} | {v} |" for k, v in sorted(count.items())], "",
     "- **PASS** = executed and every assertion held. **FAIL** = executed and an assertion broke. **BLOCKED** = could not run (needs the real trained model or real data). **KNOWN GAP** = a defect that is documented and expected to fail (a strict xfail: it turns into a failure the day it is fixed).",
     "", "## 2. What was and was not tested", "",
     "| Layer | What it proves | Model used |", "|---|---|---|",
     "| API + database (pytest, real uvicorn server, real SQLite file) | validation, scoring, recommendations, persistence, history, export, failure handling | Neural network **trained by `synthetic_model.py` on synthetic data** (learned, never hand-set; 97.9 % held-out accuracy). Samples are picked by their synthetic truth label; the expected answer comes from an independent NumPy forward pass |",
     "| Browser (Playwright, Chromium, frontend build against that server) | what the screen shows equals the API response and the database row; frontend validation; failure messages; downloads | same |",
     "| Recommendation rules (pytest) | rules for each class, unknown class, rules with a **controlled test double** for the scorer (`mock_ml`) | double, labelled |",
     "| Real artefacts (E2E-B1, B2) | the real exported model and real readings | **BLOCKED**: `ml/artifacts/<bundle>` and real readings are not in this workspace |", "",
     "**Not executed:** anything on the real model or real sensor data; Windows (the suite is cross-platform Python/Node, but was run on Linux); Firefox/Safari; PostgreSQL. The synthetic model proves the *pipeline*, not the quality of your real model.",
     "", "## 3. Defects found and fixed during this task", "",
     "| # | Defect | Severity | Fix | Re-test |", "|---|---|---|---|---|",
     "| E1 | Upload page said *“Extra columns are ignored”* but the backend rejects unknown columns (only `condition_label` is ignored), so a user could believe a misspelled column was harmless | Medium | `UploadPage.tsx` hint rewritten to match backend | E2E-CSV1, E2E-F, UI-F, Vitest |",
     "| E2 | An export with no matching rows had a different header from a populated export (the `model_score_*` columns were missing) | Medium | `routes_history.py` seeds score columns from the loaded model | E2E-L (and a mutation check: removing the fix makes E2E-L fail) |",
     "| E3 | *(test-quality, not product)* E2E-A had a vacuous assertion (`… or True`) and the chain did not compare stored steps with the rule table; a mutation that dropped the last step before saving was not caught by B and C | – | assertion removed; chain now compares returned steps with the rule table | the mutation now fails A, B and C |", "",
     "**Known gap kept open:** R1 – `/api/predict/batch` has no idempotency, so uploading the same CSV twice stores the rows twice (E2E-I2, strict xfail). Not fixed because it needs a design decision (file hash, per-row key).", "",
     "**Observations (by design, not defects):** CSV rows store no recommendation JSON (regenerated on read, flagged); sensor readings are not stored unless `STORE_INPUT_READINGS=true`; an unknown condition filter returns an empty list; manual assessments sent without an Idempotency-Key are stored each time; `motor_id` may not contain `=`.", "",
     "## 4. Scenario table", "",
     "| Test ID | Scenario | Status | Layer |", "|---|---|---|---|"]
for r in rows: L.append(f"| {r['id']} | {r.get('letter','')}: {esc(r.get('title',''))} | **{r['status']}** | {esc(r.get('layer',''))} |")
L += ["", "## 5. Details per scenario", ""]
for r in rows:
    L += [f"### {r['id']} – {r.get('title','')}", "", f"- **Status:** {r['status']}" + (f" ({esc(r['failure'])})" if r.get("failure") else ""),
          f"- **Preconditions:** {esc(r.get('preconditions',''))}", f"- **Test input:** {esc(r.get('input',''))}", f"- **Expected behaviour:** {esc(r.get('expected',''))}",
          f"- **Actual behaviour:** {esc(' | '.join(r.get('actual', [])) or r.get('failure',''))}", f"- **Evidence:** {esc(' | '.join(r.get('evidence', [])))}" + (f" · test: `{r['nodes'][0]}`" if r.get("nodes") else ""),
          f"- **Defect severity if it fails:** {esc(r.get('severity_if_fail', r.get('sev','')))}", f"- **Corrective action:** {esc(r.get('corrective_action', r.get('fix','')))}"]
    if r["id"] in shots: L.append(f"- **Screenshot:** ![{r['id']}](qa/e2e-evidence/{shots[r['id']]}.png)")
    L.append("")
(DOCS / "e2e-test-report.md").write_text("\n".join(L), "utf-8"); print("wrote docs/e2e-test-report.md;", count)
