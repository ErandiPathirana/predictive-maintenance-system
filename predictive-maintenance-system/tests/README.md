# Tests

| Where | What | Run |
|---|---|---|
| `tests/backend/` | Backend unit, API and Colab-contract tests (pytest) | `cd backend` then `python -m pytest` |
| `frontend/src/**/*.test.ts(x)` | Frontend component and API-client tests (Vitest) | `cd frontend` then `npm test` |

Frontend tests live beside their code, which is the Vite/Vitest convention and avoids Node package-resolution problems. See `tests/frontend/README.md`.

All test models use **random data** and exist only to check the software. Their output is never a research result.

The full plan and the manual checklist are in `docs/testing-plan.md`.
