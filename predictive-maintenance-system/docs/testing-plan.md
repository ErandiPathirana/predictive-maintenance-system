# Testing plan

## Levels of testing

| Level | Tool | Where | What it proves |
|---|---|---|---|
| Backend unit | pytest | `tests/backend/test_services.py` | Validation, preprocessing and model loading behave correctly on their own. |
| Backend API | pytest + FastAPI TestClient | `tests/backend/test_api.py` | Endpoints, status codes, error format, CORS and docs. |
| Colab-to-backend contract | pytest | `tests/backend/test_ml_export_contract.py` | Files exported by the Colab helper load and predict in the backend; common mistakes are rejected. |
| Frontend unit and component | Vitest + Testing Library | `frontend/src/**/*.test.tsx` | Components and the API client handle loading, success and error states. |
| Manual and usability | Checklist | below | Real use on real devices. |

Frontend tests sit next to the code they test (the standard Vite/Vitest convention) because Node resolves packages relative to the test file. `tests/frontend/README.md` points to them.

**Important:** test models use random data and only check the software. Their outputs are never research results.

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
