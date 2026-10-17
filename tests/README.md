# Tests

| Where | What | Run |
|---|---|---|
| `tests/backend/` | Backend unit + integration tests (pytest) | `cd backend` then `python -m pytest` |
| `frontend/src/**/*.test.ts(x)` | Frontend tests (Vitest) | `cd frontend` then `npm test` |

Test bundles use random weights and only check the software; their output is never a research result.
To check a REAL bundle against the contract: `$env:PM_TEST_BUNDLE_DIR="ml\artifacts\pm_condition_ann_v1.0.0"; python -m pytest -k real_notebook`.
See `docs/testing-plan.md`.
