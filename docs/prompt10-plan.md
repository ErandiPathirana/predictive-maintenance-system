# Prompt 10 implementation plan (manual entry, recommendations, history)

## What already exists (inspected)
| Need | Status in the repository |
|---|---|
| Trained-model loading, exact feature order, class mapping, preprocessing | Done (`artifacts.py`, `inference.py`). 14 inputs including rotational speed and load |
| Single prediction `POST /api/predict` (motor_id, measured_at, readings, strict validation) | Done. No motor name, operator or recommendations |
| Batch CSV `POST /api/predict/batch`, validation dry run, template, export | Done. Row-level errors returned; no recommendations in results |
| History `GET /api/predictions` with filters; detail by id; export | Done. Raw readings **not stored** by default (`STORE_INPUT_READINGS=false`) |
| Frontend: Dashboard, Monitoring, Upload, Results, History, Evaluation, Research | Done. No manual-entry form |
| Recommendation engine | **Stage 1 (this stage)** |

## Decisions that need you (they change what is stored)
1. **Store sensor readings with each assessment?** "Compare readings over time" and "summary of important readings" in history need them. It is off today for privacy. Turning it on stores sensor values in your database (`STORE_INPUT_READINGS=true`).
2. **Operator identifier.** There is no user login, only an optional shared API key. A typed operator name cannot be trusted as identity. Proposed: optional free-text "recorded by", labelled as unverified.
3. **Site-approved procedures or thresholds.** None exist yet. Until you supply them, every recommendation is labelled general guidance.

## Stages (each one tested, then you confirm before the next)
1. **Recommendation engine** (backend module, tests, rules documentation). *Done in this stage.*
2. **Backend assessment API**: `POST /api/assessments` (manual entry, optional equipment description and recorded-by, idempotency key against double submit, recommendations in the response, saved only after the database confirms), database migration, recommendations in batch results and exports, optional site-guidance loading.
3. **Frontend "New Motor Assessment"** form and result page (validation, clear form with confirmation, loading state, print).
4. **History**: assessment detail with recommendations, readings comparison over time (if stored), export.
5. **CSV improvements**: cancel, per-row error view, recommendations in downloaded results.
6. **Documents**: user guide, safety and intended-use statement, test report, screenshots.
