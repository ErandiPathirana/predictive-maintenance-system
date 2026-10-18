# Backend QA report

Scope: the FastAPI backend in `backend/app`. Architecture unchanged. Twelve defects were found by testing; each was fixed at its root cause, and the tests that exposed it now pass.

## 1. What was and was not tested

| Kind | Meaning | Used for |
|---|---|---|
| **real_artifacts** | The trained model bundle from the Colab notebook | **BLOCKED.** `ml/artifacts/` contains only `.gitkeep`. No trained bundle exists in the project, so 6 tests were skipped. A skip is not a pass. |
| **synthetic_bundle** | Real loader, real inference code, real database, but made-up weights | Almost everything else. Proves the software works. Says nothing about model accuracy. |
| **mock_ml** | The model is replaced by a stub | 4 tests only (marked `@pytest.mark.mock_ml`), to check how the backend reacts to a broken or fixed inference step. |

Forced bundles (weights that always select output *k*) were used to test class mapping without mocking anything.

Executed on **Linux**, Python **3.12.3** (your version) and **3.13.16**, FastAPI 0.115.14, pydantic 2.10.6, SQLAlchemy 2.0.55. **Not executed on Windows.**

## 2. Run it in Windows PowerShell

```powershell
cd <your-project>\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # if blocked: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
python -m pip install -r requirements-dev.txt

python -m pytest                                  # everything (existing + QA): 535 tests
python -m pytest -k test_qa                       # QA suite only
python -m pytest -k "test_qa_05"                  # one file (01..07)
python -m pytest -vv -rfsx | Tee-Object ..\docs\qa\my-run.txt   # full per-test output saved to a file
python -m pytest --junitxml=..\docs\qa\junit.xml  # machine-readable results

# When you have the trained model exported from Colab:
$env:PM_TEST_BUNDLE_DIR = (Resolve-Path ..\ml\artifacts\pm_condition_ann_v1.0.0).Path
python -m pytest -m real_artifacts -rs            # the 6 BLOCKED tests now run for real
Remove-Item Env:PM_TEST_BUNDLE_DIR
```

Always run from the `backend` folder (that is where `pytest.ini` is). Do not pass a test file path from another folder: use `-k`.

## 3. Results (final run, Python 3.12.3)

**527 passed, 7 skipped (6 BLOCKED + 1 older opt-in test), 1 expected failure (known gap), 0 failed.** Same on Python 3.13.16.
Raw output: `docs/qa/backend-qa-output-after-fix.txt`.

| # | Area | Result | New QA tests | Notes |
|---|---|---|---|---|
| 1 | Startup and shutdown | **PASS** | 7 | Includes a real `uvicorn` process: starts, serves, shuts down cleanly, reads environment variables, refuses to start without a model |
| 2 | Load the *trained* model + preprocessing | **BLOCKED** | 4 skipped | No trained bundle exists. Loader logic is proven on synthetic bundles (areas 1, 7) |
| 3 | Health and model-info | **PASS** | 4 | |
| 4 | Manual assessment endpoint | **PASS** | 3 + many in 6 | |
| 5 | CSV upload and batch | **PASS** | 6 + many in 6, 15 | Includes a 5,000-row file under the default 2 MB limit |
| 6 | Input validation | **PASS** | 159 | Missing, wrong types, bad timestamps, NaN, infinity, absurd numbers, malformed JSON and CSV |
| 7 | Unknown motors, missing artifacts | **PASS** | 26 | |
| 8 | Same input, same result | **PASS** (synthetic) / **BLOCKED** (trained model) | 6 + 1 skipped | Bit-identical across calls, routes, batch size, row order, restarts |
| 9 | Output to Normal/Alert/Danger | **PASS** (synthetic) / **BLOCKED** (trained model) | 7 + 1 skipped | Follows `class_mapping.json`, not a hard-coded order |
| 10 | Class to corrective action | **PASS** | 7 | |
| 11 | Database writes, reads, transactions | **PASS** | 14 | Fault injection: failed batch leaves no rows and no orphan batch |
| 12 | Export and filters | **PASS** | 10 | Inclusive date boundaries, truncation flag, spreadsheet-formula safety |
| 13 | HTTP status codes and messages | **PASS** | 2 + many | One error shape everywhere |
| 14 | CORS and environment variables | **PASS** | 19 | |
| 15 | File-size and row limits | **PASS** | 7 | Exact boundary tests |
| 16 | Logging, exceptions, leakage | **PASS** | 13 | |
| 17 | Duplicates and invalid requests | **PASS** with **1 known gap** | 12 + 1 expected failure | See risk R1 |
| 18 | API docs and schema consistency | **PASS** | 10 | Real responses validated against the published OpenAPI schemas |

The 215 older tests also still pass.

**Counts are by test-name tag.** A test that checks CSV limits and validation may be tagged to only one area.

## 4. How good are the tests?

- **Before the fixes:** run against the original code, 51 tests failed (`docs/qa/backend-qa-output-before-fix.txt`). The 215 older tests passed, so the defects were genuinely new findings.
- **Mutation check:** 17 deliberate bugs were put into a scratch copy (reversed class mapping, wrong advice for Danger, off-by-one limits, removed auth, removed formula protection, scaling skipped, NaN allowed, and others). The suite caught **16**. The one that survived (removing the explicit `rollback()` in the batch route) is harmless: the session is discarded at the end of every request, which rolls back anyway.
- **Stability:** the 8-thread duplicate-submission test passed 5 of 5 repeated runs, and the whole suite passed in 3 consecutive runs after the last change (see the stability line in section 3 if it differs).

## 5. Defects found and fixed

Severity here means impact on a hosted deployment: **Medium** = a client can trigger a server error or wrong behaviour with one request; **Low** = hygiene.

| ID | Sev. | Defect (reproduced first) | Root cause | Fix | Files |
|---|---|---|---|---|---|
| D1 | Medium | A finite but absurd reading such as `1e308` returned **500** `prediction_failed` (JSON and CSV) | Value overflowed inside the network; result was treated as a server fault | If scores are non-finite and the standardised input is absurd (>1e100), answer **422**; sane input with bad output stays a 500 | `services/predictions.py` |
| D2 | Medium | A 400-digit integer returned **500** | `float()` raises `OverflowError`, which was not caught | New `_is_finite_number` treats it as invalid (422) | `services/predictions.py` |
| D3 | Medium | A timezone-aware date such as `9999-12-31T23:59:59-05:00` returned **500** | Conversion to UTC overflowed | Caught and reported as a 422 | `schemas.py` |
| D4 | Low | JSON endpoints accepted any year 0001 to 9999 while CSV allows 1970 to 2100 | Two different rules | One shared rule (`MIN_YEAR`/`MAX_YEAR`), judged in UTC | `schemas.py`, `services/csv_io.py` |
| D5 | Low | A 500 response had no `X-Request-ID`, `nosniff` or `no-store` | The outermost error handler bypasses the request middleware | Handler adds the headers itself; request ID passed via `request.state` | `main.py`, `core/errors.py` |
| D6 | Medium | 100,000 unknown reading names produced an ~890 KB error echoing every name | No limit on `readings` size | At most 100 readings (model has 14) | `schemas.py` |
| D7 | Low | CSV accepted Arabic-Indic and full-width digits as numbers | `\d` matches all Unicode digits | ASCII digits only | `services/csv_io.py` |
| D8 | Medium | Database failure on `/predict`, `/predict/batch` and all reads returned **500**; only assessments returned 503 | No general database error handling | One handler: **503** `database_unavailable`, driver text never returned or logged | `core/errors.py` |
| D9 | Low | Zero or negative size/row limits and unknown log levels were accepted; non-ASCII `API_KEY` could never match | No config validation | Limits must be greater than 0; log level restricted to the 5 valid names (any case); `API_KEY` printable ASCII | `core/config.py` |
| D10 | Low | `/api/predict` turned a bare number such as `12345.5` into a 1970 date | The "timestamp must be text" guard existed only on assessments | Same guard on both | `schemas.py` |
| D11 | Medium | `GET /api/predictions/99999999999999999999999999` returned **500** | Integer too big for the database column | Row IDs limited to 1 to 2⁶³−1 (422) | `api/deps.py`, both history/assessment routes |
| D12 | Medium | CSV with an aware date such as `0001-01-01T00:00:00+05:00` returned **500** | Same overflow as D3, in the CSV path | Caught and reported per row | `services/csv_io.py` |

Other changes: `docs/openapi.json` and `docs/api-schemas.md` regenerated (they were correctly flagged as stale after the schema changes), and `jsonschema` added to `requirements-dev.txt`.

No test was weakened to pass. Several of my own test mistakes were corrected along the way (a wrong exit-code assumption for `uvicorn`, a test that relied on random weights, a test that read the client's log instead of the server's log). One mistake was in a fix: my first version of the row-ID limit shared one FastAPI `Path()` object between two routes, which broke both; the tests caught it and it now uses a fresh object per route.

## 6. Remaining backend risks

| ID | Risk | Sev. | Detail and suggestion |
|---|---|---|---|
| R1 | **Duplicate submissions on `/predict` and `/predict/batch`** | Medium | Only `/api/assessments` accepts an `Idempotency-Key`. Uploading the same CSV twice stores it twice. Test `test_a17_known_gap_...` is an expected failure that will start passing (and then fail loudly, `strict`) when this is fixed. Needs a new column, so a migration. |
| R2 | **The trained model has not been tested** | High for any claim about the model | Every model-dependent test used made-up weights. Run `-m real_artifacts` once you have a bundle. |
| R3 | **No limit on JSON request size** | Medium if hosted | Only CSV uploads have a size limit. Large JSON bodies are parsed before validation. Set a limit in the reverse proxy. |
| R4 | **No login; optional shared key; no rate limit** | Medium if hosted | `API_KEY` is not required even in production mode. One shared secret, no per-user identity (`recorded_by` is free text). |
| R5 | **PostgreSQL untested** | Medium if hosted | All database tests ran on SQLite. Migrations and the `postgres://` normalisation are checked, but not against a live PostgreSQL server. |
| R6 | **Not run on Windows** | Low | The process-level test cannot check graceful shutdown there (Windows terminates the process). Please run section 2 and report anything that differs. |
| R7 | `GET /api/assessments/{id}` needs the model loaded | Low | It only reads stored data but answers 503 when the model is missing. |
| R8 | Exact score ties pick `Normal` | Low | Recorded as a deliberate, tested behaviour. A tie in floating-point scores is practically impossible. |
| R9 | Export has no UTF-8 BOM | Low | Excel may show non-ASCII text (for example `Pümpe`) wrongly when double-clicked. Import via Data > From Text/CSV. |
| R10 | No engineering limits on readings | By design | Values outside the training range only produce a warning, so `-500` degrees is accepted. |
| R11 | Frontend and backend contract | Not covered | This audit is backend only. |
