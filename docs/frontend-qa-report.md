# Frontend QA and usability report

Scope: the React + TypeScript app in `frontend/`, used by machine operators, maintenance technicians and plant engineers.
Architecture unchanged (React 19, Mantine 9, HashRouter, Vite). Nine defects were confirmed by running the app and fixed at the cause.

## 1. What was and was not executed

| Executed | How |
|---|---|
| Type-check, production build | `tsc --noEmit`, `vite build`: clean |
| Unit/component tests | Vitest, **92 passed** (86 existing + 6 new regression tests; the skip-link test was mutation-checked: it fails when the fix is removed) |
| **Browser end-to-end tests** | Playwright 1.56 driving headless **Chromium** on **Linux**, against the **real built frontend** and the **real FastAPI backend** (real model loader, real database). **89 tests: 88 PASS, 0 FAIL, 1 N/A** (`docs/qa/frontend-e2e-results.md`) |
| Accessibility scan | axe-core 4.10.2, WCAG 2.0/2.1/2.2 A+AA rules, 6 pages x desktop + mobile, plus the validation-error state and the Normal/Alert/Danger result pages: **14 scans, 0 violations** (`docs/qa/frontend-axe-results.json`) |
| Layouts | Chromium **emulated** viewports 1280, 768 and 375 px wide, all 6 pages and the full assessment flow |
| Screenshots | `tests/e2e/evidence/` (69 images), selection in `docs/qa/frontend-evidence/` |

**Not executed (do not read these as passed):** real phones/tablets, touch input, Windows, Firefox, Safari, Edge, any screen reader, the access-key (X-API-Key) dialog, print preview, a 5,000-row upload in the UI, the monitoring date-range filter, the **trained** model (every prediction below came from a test model with made-up weights that always returns the requested class; it tests the software, not model quality), PostgreSQL. Axe finds only about a third of accessibility problems; the manual checklist covers the rest.

## 2. Test cases and results (by requested workflow)

| # | Workflow | Tests (IDs in the results file) | Result |
|---|---|---|---|
| 1 | Open the assessment form | E01 (title, 14 inputs, labels, fieldset groups, active menu item) | PASS |
| 2 | Select/enter a motor ID | E02 (type new ID, saved, then offered as suggestion; chosen with the keyboard) | PASS |
| 3 | Measurement timestamp | E03 (Use now, future-time warning, empty time is an error) | PASS |
| 4-5 | Enter all readings, submit, get the real backend prediction | E05-NOR/ALE/DAN, E06d (keyboard only), E17 (double-click gives exactly 1 record) | PASS |
| 6 | Correct invalid fields | E06 (16-item summary, focus moves to it, entries kept; `abc`, `1,5`, `1e999`, empty, negative each get a plain message; `aria-invalid`; fix and resubmit), E06c, E06e, E06f (server 422), E13d (server 500, retry) | PASS |
| 7 | Valid CSV and preview | E07a (5-row preview, check, analyse, results), E07t (template) | PASS |
| 8 | Malformed CSV | E08 x10: missing column, letters, blank, bad date, header only, empty file, `.txt`, binary, NaN/Infinity, ragged row. Each is rejected with row and column or a plain reason; Analyse stays disabled | PASS |
| 9 | Condition and corrective actions | E09-NOR/ALE/DAN (see section 3) | PASS |
| 10 | History | E10 (list, open detail) | PASS |
| 11 | Filter and export | E11a, E11b (download, only filtered rows, `.csv`), E11c (inverted dates blocked) | PASS |
| 12 | Sensor trends and evaluation metrics | E12a-c: trends/dashboard PASS. **E12d: N/A**, there is no evaluation-metrics screen; `docs/frontend.md` says it was removed on purpose | PASS / N/A |
| 13 | Outage, loading, no model | E13-out-a..d (server off; server dies mid-submit and comes back), E13-slow-a..c (3 s delay, busy button, 20 s time-out message), E13-nomodel-a..c | PASS |
| 14 | Desktop, tablet, mobile | E14 x21 (no sideways scroll, menu works, result not clipped) | PASS |
| - | Keyboard | K01-K05 (skip link, focus rings on every Tab stop of every page, page-change announcement, mobile menu, 200% text) | PASS |
| - | Accessibility | A11Y x15 (axe) | PASS |

## 3. Condition-to-action mapping and safety rules

Checked in the real browser for all three classes (E05, E09). The check reads the whole rendered result and fails on invented deadlines (`within 2 hours`), parts or repairs (`replace`, `new bearing`), automatic-shutdown claims, invented thresholds (`exceeds the limit`) and fault diagnoses.

| Class | What the user sees | Verdict |
|---|---|---|
| Normal | Routine monitoring guidance; no red notice | PASS |
| Alert | Inspect, inform the maintenance engineer, qualified inspection | PASS |
| Danger | Word + diamond + "Predicted condition". Dark-red box "Contact the responsible maintenance engineer now". "Not a confirmed fault and not a shutdown order". Stop or isolate "only through the site's approved shutdown, lockout/tagout and authorisation procedures". "Do not open electrical equipment, remove guards or touch moving parts unless you are qualified and authorised". Inspection before return to service "where site procedures require it" | PASS |

All three show "A predicted condition is a statistical estimate. It is not a confirmed machine failure, and it does not say when anything will fail", say scores are not calibrated probabilities, and state that no engineering thresholds are configured. Time wording is only "Immediate safety review" / "Prompt engineering assessment", with no numbers. The Alert checklist word "lubrication issues" is an inspection item ("look for ..."), not a repair instruction.

## 4. Defects found and fixed

Severity is for the intended users: **High** blocks or endangers a task, **Medium** makes it hard or fails WCAG AA, **Low** is polish.

| ID | Sev. | Defect (reproduced first) | Root cause | Fix | Files |
|---|---|---|---|---|---|
| F1 | **High** | Keyboard users pressing **Skip to main content** landed on "Page not found" | HashRouter reads `#main` as the route `/main` | Click handler cancels the jump and moves focus to `<main>` | `AppLayout.tsx` |
| F2 | Medium | Text fields showed focus only as a 1 px border colour change; easy to miss in a plant | Mantine default | 3 px ring on all inputs | `global.css` |
| F3 | Medium | Static notices ("Read with care") were announced as urgent alerts on every page load | Mantine `Alert` defaults to `role="alert"` | `role="note"` / `role="status"` for non-urgent notices; real errors and the Danger notice keep `role="alert"` | `DemoNotice.tsx`, `AssessmentResult.tsx`, `UploadPage.tsx`, `AssessPage.tsx` |
| F4 | Medium | Page title never changed and focus stayed put after navigating (WCAG 2.4.2); screen-reader users were not told the page changed | Single-page app | Title per page; focus moves to main on navigation | `AppLayout.tsx` |
| F5 | **High for this app** | The **Danger notice** (white on red `#fa5252`) had only **3.28:1** contrast; same for red buttons | Default red shade | Darker red palette (`#b3261e`, 6.5:1 with white) | `theme.ts` |
| F6 | Medium | Server off: **New assessment** showed two overlapping boxes ("No model is loaded" and "could not be checked"), the first wrong (the model may be fine), and **no Try again button** | Both components rendered; retry not wired | One box, retry wired to reload | `AssessPage.tsx`, `DemoNotice.tsx` |
| F7 | Low | "Readings used" listed raw column names such as `nde_v_temp_c` | Raw key displayed | "Non-drive end, vertical: Temperature (nde_v_temp_c)", same words as the form | `AssessmentResult.tsx` |
| F8 | Medium | Grey help text under every field and page subtitles: **2.81:1**; placeholder **2.07:1**; error text **3.6:1** | Mantine default greys/red | Darker tokens (help text 5.9:1 on the page background, placeholder 5.8:1, error 6.5:1) | `global.css` |
| F9 | Medium | Labels on recommendation cards ("Who: ...", timing, "General guidance") were 11 px grey/orange at **2.7-3.0:1**, and **cut off on phones** ("ho: Responsible maintenance engine") | Default light/outline badges with no-wrap | Own 13 px style, 4.5:1 or better, wraps | `AssessmentResult.tsx`, `global.css` |
| F10 | Low | "Key (access)" button and the brand link were under 24 x 24 px (WCAG 2.2 target size) | Compact button size | Larger size and padding | `AppLayout.tsx`, `global.css` |

Regression tests added: Vitest `components/layout.test.tsx` (F1, F4, F5), `pages/assess.test.tsx` (F6, F7), plus the 89 browser tests (F2, F3, F8-F10 through axe, the focus-ring test and the clipping test). The final run has 0 failures; the intermediate runs failed on F1, F5, F6, F8 and F9 before they were fixed.

One test correction to be transparent about: my keyboard focus-ring test first failed on the browser's own date-picker icon (Chromium draws that ring itself); the test now skips that icon. Another earlier failure was my own test reading the wrong alert; both were test errors, not application defects.

## 5. Remaining usability problems (not changed)

| ID | Problem | Suggestion |
|---|---|---|
| U1 | No screen for model evaluation metrics (removed deliberately). `getEvaluationReport` and `lib/evaluation.ts` are now unused code | Delete the dead code or restore a read-only page for the thesis |
| U2 | Bad-date message from the server contains a programmer format `%m/%d/%Y %H:%M`, while the page hint says `YYYY-MM-DD HH:MM:SS` | Show one plain example, e.g. `2025-04-01 07:20` |
| U3 | The form shows the time in local time but the saved record says "(UTC)": two time zones on one screen | Show both or state the zone beside "Readings taken" |
| U4 | Each of the 5 recommendation cards repeats "General guidance" and "Requires maintenance-engineer confirmation" | Say it once above the list |
| U5 | CSV preview shows the first 8 of 17 columns; "1 rows" grammar | Horizontal scroll with all columns; "1 row" |
| U6 | "Key (access)" is unclear for new users | Rename "Access key" and explain when it is needed |
| U7 | Main script is 570 kB (build warning) | Acceptable for a prototype; split if it grows |
| U8 | The 14 numeric fields accept any number (e.g. 250 degrees) with only a note | By design (no approved thresholds); keep the note |

## 6. How to repeat
`tests/e2e/README.md` (browser tests), `cd frontend; npm test` (unit), and `docs/frontend-manual-test-checklist.md` (beginner checklist, including the real-device and screen-reader steps that were not run here).
