# Testing plan

## Levels of testing

| Level | Tool | Where | What it proves |
|---|---|---|---|
| Configuration and safety rules | pytest | `test_config.py` | URL normalisation; production refuses unsafe settings |
| Artifact contract | pytest | `test_artifacts.py` | Missing/tampered/inconsistent/pickled/smoke-test bundles are refused with clear messages |
| Inference and CSV unit tests | pytest | `test_inference_and_csv.py` | NumPy forward pass equals an independent reference; every CSV failure mode is detected and located |
| API integration | pytest + TestClient | `test_api_system_and_predict.py`, `test_api_history_and_reports.py` | Endpoints, strict types, all-or-nothing batches, history filters, export, formula-injection protection |
| Security and reliability | pytest | `test_security_reliability.py` | CORS, API key, no leaked internals, no sensitive data in logs (incl. uvicorn's query strings), startup failures, degraded mode |
| Database | pytest + Alembic | `test_database_and_contract.py` | Migrations create exactly the model schema; app starts on a migrated database |
| Real bundle contract | pytest (opt-in) | `PM_TEST_BUNDLE_DIR=<bundle> python -m pytest -k real_notebook` | A real notebook bundle satisfies the contract |
| Frontend | Vitest + Testing Library | `frontend/src/**/*.test.tsx` | Loading, ready, not-loaded, database-fault, error-and-retry states |
| Frontend (browser) | Playwright + Chromium, real backend, axe-core | `tests/e2e/` | Workflows, safety wording, keyboard, contrast, layouts, outage (see `docs/frontend-qa-report.md`) |
| Manual / usability | checklist | below | Real use on real devices |
| Backend QA audit (18 areas) | pytest | `test_qa_01_*.py` to `test_qa_07_*.py`, helpers in `qa_support.py` | Startup/shutdown, trained-model loading (BLOCKED until a bundle exists), input validation, CSV limits, class and recommendation mapping, database faults, export, CORS/config, logging/leaks, API docs. Full report: `docs/backend-qa-report.md` |

Test models use **random weights** and only check the software. Their outputs are never research results.
The suite was also checked by *mutation*: deliberately breaking the code (CSV-formula protection, all-or-nothing batches, log hygiene, scaling, CORS) makes the matching tests fail.

## Manual test checklist (current stage)

| # | Test | Expected |
|---|---|---|
| 1 | Start backend with no model files, open `/api/v1/health` | `status: ok`, `model_ready: false` |
| 2 | Open `/docs` | Swagger page loads |
| 3 | Open the frontend with backend running | Server "Running", Model "Not loaded" with a reason |
| 4 | Stop the backend, reload the frontend | Server "Not reachable", error notice and Try again button |
| 5 | Start backend again, click Try again | Server "Running" |
| 6 | Resize browser to phone width | No horizontal scrolling, text readable |
| 7 | Keyboard only: Tab to the button | Visible focus outline |
| 8 | After exporting artifacts: run `validate_artifacts.py` | `Smoke test OK` |
| 9 | Restart backend with artifacts | Model "Ready" with details |

## Planned for later stages
Prediction form tests, boundary and invalid-input tests against your real feature ranges, latency measurements, cross-browser and cross-device checks on the deployed site.
