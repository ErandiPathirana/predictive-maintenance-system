// Browser layer of the full-stack end-to-end tests. The UI is driven like a user; what it shows is compared with the API and with the
// DATABASE FILE (read with plain sqlite3 through tests/e2e_full/db_query.py). Needs: frontend preview on :5173 built for http://localhost:8000.
import { execFileSync, spawn } from "node:child_process";
import { readFileSync, writeFileSync, mkdirSync, existsSync, rmSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { launch, closeBrowser, FRONTEND, VIEWPORTS, fillAssessment, shot, EVIDENCE } from "./lib.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const FULL = join(HERE, "..", "e2e_full");
const OUT = join(FULL, "out");
const PY = process.env.PM_PYTHON ?? "python";
const BUNDLE = join(OUT, "bundle");
const DB = join(OUT, "ui.db");
const API = "http://localhost:8000";
const FEATURES = ["de_h_velocity_mm_s", "de_h_ge", "de_h_temp_c", "de_v_velocity_mm_s", "de_v_ge", "de_v_temp_c", "nde_h_velocity_mm_s", "nde_h_ge", "nde_h_temp_c", "nde_v_velocity_mm_s", "nde_v_ge", "nde_v_temp_c", "rotational_speed_rpm", "load_percent"];
const EXPORT_COLS = ["prediction_id", "batch_id", "source", "record_id", "motor_id", "measured_at", "predicted_at_utc", "predicted_condition", "predicted_class_id", "model_score_Normal", "model_score_Alert", "model_score_Danger", "model_version", "label_provenance_provisional", "demonstration_only", "equipment_description", "recorded_by_unverified", "recommendation_summary", "recommendation_ruleset", "note"];
const SAMPLES = JSON.parse(readFileSync(join(OUT, "samples.json"), "utf8")).samples;

const dbRows = (where = "1=1") => JSON.parse(execFileSync(PY, [join(FULL, "db_query.py"), DB, where], { cwd: FULL, encoding: "utf8" }));
const dbCount = () => dbRows().length;
const uid = (p) => `${p}-${Date.now() % 1000000}`;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const need = (c, m) => { if (!c) throw new Error(m); };
const sameJSON = (a, b) => JSON.stringify(a) === JSON.stringify(b);

let server;
async function startServer({ noModel = false, fresh = false } = {}) {
  await stopServer();
  if (fresh && existsSync(DB)) rmSync(DB);
  const args = [join(FULL, "harness.py"), "serve", "--bundle", noModel ? join(OUT, "no_such_bundle") : BUNDLE, "--db", DB, "--port", "8000", ...(noModel ? ["--no-model"] : [])];
  server = spawn(PY, args, { cwd: FULL, stdio: "ignore" });
  for (let i = 0; i < 120; i++) { try { const r = await fetch(API + "/api/health"); if (r.ok || r.status < 600) return; } catch {} await sleep(250); }
  throw new Error("backend did not start");
}
async function stopServer() { if (server && server.exitCode === null) { server.kill("SIGTERM"); await sleep(600); } server = null; }

const META = {};
const results = [];
/** reg: documentation fields; fn(page, rec) where rec.actual(text) / rec.evidence(text) collect report text. */
async function scenario(id, letter, title, meta, fn, { viewport = "desktop" } = {}) {
  META[id] = { id, letter, title, layer: "Frontend + backend + database (trained synthetic model)", severity_if_fail: "High", ...meta };
  const context = await globalThis.browser.newContext({ viewport: VIEWPORTS[viewport], acceptDownloads: true });
  const page = await context.newPage();
  const rec = { a: [], e: [], actual: (t) => rec.a.push(String(t)), evidence: (t) => rec.e.push(String(t)) };
  const r = { id, status: "PASS", actual: rec.a, evidence: rec.e, failure: "", nodes: ["suite_full.mjs"] };
  try { await fn(page, rec); } catch (e) { r.status = String(e.message).startsWith("BLOCKED") ? "BLOCKED" : "FAIL"; r.failure = String(e.message).split("\n")[0].slice(0, 500); try { await shot(page, `FULL-${id}-FAIL`); } catch {} }
  await context.close(); results.push(r);
  console.log(`${r.status.padEnd(7)} ${id} ${title}${r.failure ? "  -- " + r.failure : ""}`);
}

async function submitForm(page, readings, motor) {
  await page.goto(FRONTEND + "/#/assess"); await page.waitForSelector("form");
  await fillAssessment(page, { motor, readings: Object.fromEntries(Object.entries(readings).map(([k, v]) => [k, String(v)])) });
  await page.getByRole("button", { name: "Analyse motor" }).click();
}
async function readResult(page) {
  await page.locator(".result-banner").waitFor({ timeout: 15000 });
  const banner = (await page.locator(".result-banner .result-banner__word").innerText()).trim();
  const actions = await page.locator(".rec-item .rec-item__body > p:first-child").allInnerTexts();
  const safety = await page.locator(".rec-item__safety").allInnerTexts();
  const saved = (await page.locator("main").innerText()).match(/(?:Saved as|saved as) assessment #(\d+)/);
  const scoreCells = await page.locator('table[aria-label], table').filter({ hasText: "Model score" }).first().locator("tbody tr").allInnerTexts().catch(() => []);
  return { banner, actions: actions.map((t) => t.trim()), safety: safety.map((t) => t.replace(/^Safety:\s*/, "").trim()), id: saved ? Number(saved[1]) : null, scoreCells, urgentBox: await page.getByTestId("danger-notice").count() };
}

async function chainUI(page, rec, cls) {
  const s = SAMPLES[cls][0]; const motor = uid(`UI-${cls}`);
  const before = dbCount();
  await submitForm(page, s.readings, motor);
  const ui = await readResult(page); await shot(page, `FULL-UI-${cls}-result`);
  need(ui.id, "UI did not show an assessment number");
  const api = await (await fetch(`${API}/api/assessments/${ui.id}`)).json();
  const rows = dbRows(`id=${ui.id}`); need(rows.length === 1 && dbCount() === before + 1, `expected exactly one new database row, got ${dbCount() - before}`);
  const d = rows[0];
  need(ui.banner === s.reference_prediction, `UI shows '${ui.banner}' but the independent reference says '${s.reference_prediction}'`);
  need(ui.banner === api.predicted_condition && ui.banner === d.predicted_condition, `condition differs: UI ${ui.banner} / API ${api.predicted_condition} / DB ${d.predicted_condition}`);
  const apiActions = api.recommendations.items.map((i) => i.action), dbActions = d.recommendations.items.map((i) => i.action);
  need(sameJSON(ui.actions, apiActions), `UI actions differ from API:\nUI ${JSON.stringify(ui.actions)}\nAPI ${JSON.stringify(apiActions)}`);
  need(sameJSON(apiActions, dbActions) && sameJSON(api.recommendations, d.recommendations), "API recommendations differ from the database JSON");
  const apiSafety = api.recommendations.items.filter((i) => i.safety_note).map((i) => i.safety_note);
  need(sameJSON(ui.safety, apiSafety), "UI safety notes differ from the database/API");
  need((ui.urgentBox > 0) === (cls === "Danger"), `urgent notice shown=${ui.urgentBox > 0} for ${cls}`);
  const txt = await page.locator("main").innerText();
  need(/not a confirmed machine failure/i.test(txt), "the 'not a confirmed failure' statement is missing next to the prediction");
  for (const c of ["Normal", "Alert", "Danger"]) { const shown = ui.scoreCells.find((r) => r.startsWith(c)); need(shown && Math.abs(parseFloat(shown.split(/\s+/).pop()) - d.scores[c]) < 0.0006, `score ${c} on screen (${shown}) != database ${d.scores[c]}`); }
  rec.actual(`truth ${cls}; independent reference ${s.reference_prediction}; screen shows '${ui.banner}' (assessment #${ui.id}); API and database both say ${d.predicted_condition}`);
  rec.evidence(`${ui.actions.length} recommendation cards on screen == API items == database JSON (${apiActions.length}); ${ui.safety.length} safety notes identical; scores on screen match the database to 3 decimals; screenshot FULL-UI-${cls}-result.png`);
  return { ui, api, d, motor };
}

function csvOf(rows, { drop = [], rename = {}, extra = {} } = {}) {
  const cols = ["record_id", "motor_id", "measured_at", ...FEATURES].filter((c) => !drop.includes(c));
  const lines = [[...cols.map((c) => rename[c] ?? c), ...Object.keys(extra)].join(",")];
  rows.forEach((r, i) => { const f = { record_id: `R${i + 1}`, motor_id: r.motor, measured_at: `2025-04-0${i + 1} 07:20:00`, ...r.readings }; lines.push([...cols.map((c) => f[c]), ...Object.values(extra)].join(",")); });
  return lines.join("\r\n") + "\r\n";
}
const writeTmp = (name, text) => { mkdirSync(join(OUT, "ui_files"), { recursive: true }); const p = join(OUT, "ui_files", name); writeFileSync(p, text); return p; };

export async function runFull() {
  globalThis.browser = await launch();
  await startServer({ fresh: true });

  for (const cls of ["Normal", "Alert", "Danger"]) {
    await scenario(`UI-${{ Normal: "A", Alert: "B", Danger: "C" }[cls]}`, { Normal: "A", Alert: "B", Danger: "C" }[cls], `Manual entry in the browser, ${cls} case: what the screen shows equals the backend answer and the saved database record`, {
      preconditions: "Backend on the trained synthetic model + fresh SQLite file; frontend build pointing at it; held-out synthetic row with truth label " + cls,
      input: "14 readings typed into the form, motor id, timestamp, then 'Analyse motor'",
      expected: "Banner word, 4-5 recommendation cards, safety notes and scores on screen == API response == sqlite row; condition == independent NumPy reference; 'not a confirmed failure' statement present; red notice only for Danger",
      corrective_action: "Compare the three sources; if only the UI differs look in AssessmentResult.tsx, otherwise in the backend",
    }, async (page, rec) => { await chainUI(page, rec, cls); });
  }

  await scenario("UI-D", "D", "Missing sensor readings: the form refuses to send and says which fields", {
    preconditions: "Form open; a baseline row count of the database", input: "each of the 14 readings left empty in turn (one at a time) and all left empty",
    expected: "inline error and error summary naming the field; NO request to POST /api/assessments leaves the browser; database unchanged", corrective_action: "assessmentForm.validateForm",
  }, async (page, rec) => {
    const before = dbCount(); let posts = 0;
    page.on("request", (r) => { if (r.method() === "POST" && r.url().includes("/api/assessments")) posts++; });
    const s = SAMPLES.Normal[1].readings;
    for (const f of FEATURES) {
      await page.goto(FRONTEND + "/#/assess"); await page.waitForSelector("form");
      await fillAssessment(page, { motor: uid("UI-D"), readings: Object.fromEntries(Object.entries(s).map(([k, v]) => [k, k === f ? "" : String(v)])) });
      await page.getByRole("button", { name: "Analyse motor" }).click();
      await page.locator(".form-summary").getByRole("alert").waitFor({ timeout: 3000 });
      need((await page.locator(".form-summary li").count()) === 1, `field ${f}: expected exactly 1 listed problem`);
    }
    await shot(page, "FULL-UI-D");
    need(posts === 0, `${posts} request(s) reached the backend`); need(dbCount() === before, "database changed");
    rec.actual("14 single omissions: each shows exactly one listed problem and an inline error; 0 requests to the backend; database row count unchanged (" + before + ")");
  });

  await scenario("UI-E", "E", "Invalid numeric values and timestamps are stopped in the browser (and the backend independently refuses them, see E2E-E)", {
    preconditions: "Form open", input: "letters, 1,5, NaN, Infinity, 1e999, 12abc, negative-looking text; empty timestamp; timestamp in the future",
    expected: "inline message in plain words; no request sent; future time shows a warning but is allowed; database unchanged", corrective_action: "assessmentForm.ts",
  }, async (page, rec) => {
    const before = dbCount(); let posts = 0; const msgs = [];
    page.on("request", (r) => { if (r.method() === "POST" && r.url().includes("/api/assessments")) posts++; });
    for (const bad of ["abc", "1,5", "NaN", "Infinity", "1e999", "12abc", "--3", "0x1F"]) {
      await page.goto(FRONTEND + "/#/assess"); await page.waitForSelector("form");
      await fillAssessment(page, { motor: uid("UI-E"), readings: Object.fromEntries(Object.entries(SAMPLES.Alert[1].readings).map(([k, v]) => [k, k === "de_h_ge" ? bad : String(v)])) });
      await page.getByRole("button", { name: "Analyse motor" }).click();
      const m = await page.locator('[data-testid="field-de_h_ge"]').evaluate((e) => e.closest(".mantine-InputWrapper-root")?.querySelector(".mantine-InputWrapper-error")?.textContent ?? "");
      need(m.length > 10, `'${bad}' produced no explanation`); msgs.push(`${bad} → ${m}`);
    }
    await page.goto(FRONTEND + "/#/assess"); await page.waitForSelector("form");
    await fillAssessment(page, { motor: uid("UI-E"), when: "2099-01-01T10:00", readings: Object.fromEntries(Object.entries(SAMPLES.Alert[1].readings).map(([k, v]) => [k, String(v)])) });
    await page.getByText("in the future").waitFor();
    await page.getByLabel("Measurement date and time", { exact: false }).fill("");
    await page.getByRole("button", { name: "Analyse motor" }).click(); await page.getByText("Measurement time").first().waitFor();
    need(posts === 0, `${posts} request(s) reached the backend`); need(dbCount() === before, "database changed");
    rec.actual(`${msgs.length} invalid texts blocked with a plain message (e.g. ${msgs[0]}); future time warns; empty time is an error; 0 requests sent; database unchanged`);
  });

  await scenario("UI-F", "F", "CSV with missing or incorrectly named columns is rejected in the browser with a reason; nothing is stored", {
    preconditions: "Upload page open", input: "CSV missing de_h_ge; CSV with 'de_h_velocity'; CSV with an unknown extra column; header-only CSV",
    expected: "plain explanation naming the column (local check or server check); 'Analyse file' stays disabled; no upload batch or prediction rows are created", corrective_action: "UploadPage.tsx / csv_io.py",
  }, async (page, rec) => {
    const before = dbCount(); const rows = SAMPLES.Normal.slice(0, 2).map((s, i) => ({ readings: s.readings, motor: `UIF-${i}` })); const seen = [];
    const files = { "missing de_h_ge": [csvOf(rows, { drop: ["de_h_ge"] }), "de_h_ge"], "misnamed de_h_velocity": [csvOf(rows, { rename: { de_h_velocity_mm_s: "de_h_velocity" } }), "de_h_velocity"], "unknown column 'comment'": [csvOf(rows, { extra: { comment: "x" } }), "comment"] };
    for (const [name, [text, col]] of Object.entries(files)) {
      await page.goto(FRONTEND + "/#/upload"); await page.getByRole("heading", { name: /Upload and analyse/ }).waitFor();
      await page.locator('input[type="file"]').setInputFiles(writeTmp(name.replace(/\W+/g, "_") + ".csv", text)); await sleep(500);
      const check = page.getByRole("button", { name: "Check file" });
      if (await check.isEnabled()) { await check.click(); await page.getByText(/File check found/).waitFor({ timeout: 10000 }); }
      const main = await page.locator("main").innerText();
      need(main.includes(col), `${name}: the message does not name '${col}'`);
      need(!(await page.getByRole("button", { name: "Analyse file" }).isEnabled()), `${name}: Analyse is enabled`);
      seen.push(name);
    }
    await shot(page, "FULL-UI-F");
    need(dbCount() === before, "database changed");
    rec.actual(`${seen.join("; ")}: each rejected with a message naming the column; Analyse disabled; database unchanged`);
  });

  await scenario("UI-CSV", "F", "Valid CSV in the browser: preview, check, analyse; the results page, history and the downloaded export agree with the database", {
    preconditions: "Upload page open", input: "6-row CSV, 2 held-out rows per class (chosen by truth label)",
    expected: "5-row preview, 'File check passed', 6 results whose conditions equal the independent reference and the 6 new database rows", corrective_action: "UploadPage / predict_batch",
  }, async (page, rec) => {
    const before = dbCount(); const sel = ["Normal", "Alert", "Danger"].flatMap((c) => SAMPLES[c].slice(0, 2).map((s, k) => ({ s, readings: s.readings, motor: `${uid("UICSV")}-${c[0]}${k}` })));
    await page.goto(FRONTEND + "/#/upload"); await page.locator('input[type="file"]').setInputFiles(writeTmp("valid6.csv", csvOf(sel)));
    await page.getByText(/Preview of the first/).waitFor(); need((await page.locator("table").first().locator("tbody tr").count()) === 5, "preview should show 5 of 6 rows");
    await page.getByRole("button", { name: "Check file" }).click(); await page.getByText("File check passed").waitFor({ timeout: 10000 });
    await page.getByRole("button", { name: "Analyse file" }).click(); await page.getByRole("link", { name: "View results" }).waitFor({ timeout: 15000 }); await shot(page, "FULL-UI-CSV-analysed");
    await page.getByRole("link", { name: "View results" }).click(); await page.getByText(/6 of 6 records/).waitFor();
    const rowsOnScreen = await page.locator("table tbody tr").allInnerTexts();
    const dbr = dbRows("source='csv'").slice(-6); need(dbr.length === 6 && dbCount() === before + 6, "expected 6 new csv rows");
    sel.forEach((x, i) => { const line = rowsOnScreen.find((t) => t.includes(x.motor)); need(line && line.includes(x.s.reference_prediction), `${x.motor}: screen '${(line ?? "not listed").slice(0, 90)}' vs reference ${x.s.reference_prediction}`); const d = dbr.find((r) => r.motor_id === x.motor); need(d && d.predicted_condition === x.s.reference_prediction, `${x.motor}: database ${d?.predicted_condition}`); });
    await page.goto(FRONTEND + "/#/upload");   // back: the analysis is kept in this browser session
    await page.goto(FRONTEND + "/#/history"); await page.locator("table tbody tr").first().waitFor();
    const [dl] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: /Export matching rows/ }).click()]);
    const lines = readFileSync(await dl.path(), "utf8").trim().split(/\r?\n/); const head = lines[0].split(",");
    need(sameJSON(head, EXPORT_COLS), "export columns differ: " + head.join(","));
    const body = lines.slice(1).join("\n"); for (const x of sel) need(body.includes(x.motor), `export lacks ${x.motor}`);
    rec.actual(`results page and database rows agree with the reference for all 6 rows (${sel.map((x) => x.s.reference_prediction).join(", ")}); export downloaded with ${lines.length - 1} data rows and the ${head.length} expected columns`);
  });

  await scenario("UI-I", "I", "Repeated submission from the browser: double click, and re-sending the identical readings, create exactly one record", {
    preconditions: "Form filled", input: "double-click 'Analyse motor'; then 'Edit these readings' and 'Analyse motor' again with identical data",
    expected: "one database row; second result says it was already saved and no second record was created", corrective_action: "AssessPage.tsx busy guard and Idempotency-Key reuse",
  }, async (page, rec) => {
    const motor = uid("UI-I"); const s = SAMPLES.Alert[2].readings;
    await page.goto(FRONTEND + "/#/assess"); await page.waitForSelector("form");
    await fillAssessment(page, { motor, readings: Object.fromEntries(Object.entries(s).map(([k, v]) => [k, String(v)])) });
    await page.getByRole("button", { name: "Analyse motor" }).dblclick(); await page.locator(".result-banner").waitFor();
    need(dbRows(`motor_id='${motor}'`).length === 1, "double click created more than one row");
    await page.getByRole("button", { name: "Edit these readings" }).click(); await page.getByRole("button", { name: "Analyse motor" }).click();
    await page.getByText(/already saved/i).waitFor({ timeout: 10000 });
    need(dbRows(`motor_id='${motor}'`).length === 1, "re-sending identical readings created a second row");
    rec.actual("double click → 1 row; identical re-send → message 'already saved … No second record was created'; still 1 row");
  });

  await scenario("UI-J", "J", "History page for an unknown motor ID", {
    preconditions: "History page with stored records", input: "Motor ID 'NO-SUCH-MOTOR' + Apply filters", expected: "plain 'No stored predictions match these filters', no error, no table", corrective_action: "HistoryPage.tsx",
  }, async (page, rec) => {
    await page.goto(FRONTEND + "/#/history"); await page.locator("table tbody tr").first().waitFor();
    await page.getByRole("textbox", { name: "Motor ID" }).fill("NO-SUCH-MOTOR"); await page.getByRole("button", { name: "Apply filters" }).click();
    await page.getByText("No stored predictions match these filters").waitFor({ timeout: 5000 });
    need((await page.locator("table tbody tr").count()) === 0, "rows shown for an unknown motor"); need((await page.getByRole("alert").filter({ hasNotText: /Read with care/ }).count()) === 0, "an error box appeared");
    await shot(page, "FULL-UI-J"); rec.actual("empty state 'No stored predictions match these filters'; no table rows; no error box");
  });

  await scenario("UI-K", "K", "A prediction saved from the form is found in History and its detail page shows the same condition, scores and steps as when it was made", {
    preconditions: "A fresh assessment", input: "save a Danger assessment, then History → filter by its motor → open it",
    expected: "same condition and same recommendation texts as the result screen and as the database", corrective_action: "AssessmentDetailPage / HistoryPage",
  }, async (page, rec) => {
    const { ui, d, motor } = await chainUI(page, { actual() {}, evidence() {} }, "Danger");
    await page.goto(FRONTEND + "/#/history"); await page.locator("table tbody tr").first().waitFor();
    await page.getByRole("textbox", { name: "Motor ID" }).fill(motor); await page.getByRole("button", { name: "Apply filters" }).click();
    await page.waitForFunction(() => document.querySelectorAll("table tbody tr").length === 1);
    const row = await page.locator("table tbody tr").first().innerText(); need(row.includes("Danger") && row.includes(motor), "history row lacks condition/motor: " + row);
    await page.locator("table tbody tr a").first().click(); const det = await readResult(page);
    need(det.banner === ui.banner && sameJSON(det.actions, ui.actions) && sameJSON(det.safety, ui.safety), "detail page differs from the result screen");
    need(sameJSON(det.actions, d.recommendations.items.map((i) => i.action)), "detail page differs from the database");
    await shot(page, "FULL-UI-K-detail"); rec.actual(`History row: ${row.replace(/\s+/g, " ").slice(0, 100)}; detail page shows ${det.banner} with the same ${det.actions.length} steps as the result screen and the database`);
  });

  await scenario("UI-L", "L", "Export from the History page: expected records and columns for a filtered selection", {
    preconditions: "Records of several classes stored", input: "filter by condition Danger, press 'Export matching rows (CSV)'",
    expected: "download with the exact column list, only Danger rows, the same number of rows the page announces, values equal to the database", corrective_action: "HistoryPage doExport / routes_history",
  }, async (page, rec) => {
    await page.goto(FRONTEND + "/#/history"); await page.locator("table tbody tr").first().waitFor();
    await page.getByRole("combobox", { name: "Predicted condition" }).click(); await page.getByRole("option", { name: "Danger" }).click(); await page.getByRole("button", { name: "Apply filters" }).click();
    await page.waitForTimeout(800);
    const announced = Number(((await page.getByText(/matching prediction/).first().innerText()).match(/([\d,]+) matching/) ?? [])[1].replace(/,/g, ""));
    const [dl] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: /Export matching rows/ }).click()]);
    const lines = readFileSync(await dl.path(), "utf8").trim().split(/\r?\n/); const head = lines[0].split(",");
    need(sameJSON(head, EXPORT_COLS), "columns differ: " + head.join(","));
    const idx = Object.fromEntries(head.map((h, i) => [h, i])); const rows = lines.slice(1).map((l) => l.split(","));
    need(rows.length === announced, `page announced ${announced} but file has ${rows.length}`);
    need(rows.every((r) => r[idx.predicted_condition] === "Danger"), "a non-Danger row was exported");
    const dbD = dbRows("predicted_condition='Danger'"); need(dbD.length === rows.length, `database has ${dbD.length} Danger rows, file ${rows.length}`);
    const byId = Object.fromEntries(dbD.map((r) => [r.id, r])); for (const r of rows) { const d = byId[Number(r[idx.prediction_id])]; need(d && Math.abs(parseFloat(r[idx.model_score_Danger]) - d.scores.Danger) < 1e-5, "score mismatch in row " + r[idx.prediction_id]); }
    rec.actual(`${rows.length} rows == page count == ${dbD.length} database Danger rows; ${head.length} expected columns; scores equal the database`);
  });

  await scenario("UI-FID", "A-C", "The screen shows what the BACKEND returns, not a value of its own", {
    preconditions: "Form filled with a Danger-labelled row", input: "the backend response is altered in flight: predicted_condition 'Danger' → 'Normal', Danger score → 0.123",
    expected: "banner shows Normal and the table shows 0.123 (the UI renders the response); with the real response the same inputs show Danger", corrective_action: "Look for hard-coded values in AssessmentResult / AssessPage",
  }, async (page, rec) => {
    await page.route("**/api/assessments", async (route) => {
      if (route.request().method() !== "POST") return route.continue();
      const resp = await route.fetch(); const j = await resp.json();
      j.predicted_condition = "Normal"; j.scores.Danger = 0.123; await route.fulfill({ response: resp, json: j });
    });
    await submitForm(page, SAMPLES.Danger[3].readings, uid("UI-FID")); const ui = await readResult(page);
    need(ui.banner === "Normal", `banner shows '${ui.banner}' although the response said Normal`);
    need(ui.scoreCells.some((r) => r.startsWith("Danger") && r.includes("0.123")), "score table ignores the response: " + JSON.stringify(ui.scoreCells));
    let src = 0; try { src = execFileSync("grep", ["-rnE", "predicted_condition *[=!]==? *\"(Normal|Alert|Danger)\"|=== *\"Danger\" *\\?", join(HERE, "..", "..", "frontend", "src", "components"), join(HERE, "..", "..", "frontend", "src", "pages"), "--include=*.tsx", "--exclude=*.test.tsx"], { encoding: "utf8" }).toString().trim().split("\n").filter(Boolean).length; } catch { src = 0; }
    rec.actual(`altered response shown as-is: banner '${ui.banner}', Danger score on screen 0.123. (The urgent red notice follows the response's own 'urgent' flag.) Static scan found ${src} comparisons of predicted_condition to a literal class in components/pages`);
  });

  // ---------- G / H need the server to change state ----------
  await scenario("UI-G", "G", "Model artifact unavailable: the browser says so and offers no assessment", {
    preconditions: "Backend restarted with no model bundle (REQUIRE_MODEL_AT_STARTUP=false)", input: "open New assessment and Upload",
    expected: "header 'no model'; New assessment explains that no prediction is made; no Analyse button; Upload cannot analyse; database unchanged", corrective_action: "AssessPage / ModelNotice",
  }, async (page, rec) => {
    const before = dbCount(); await startServer({ noModel: true });
    await page.goto(FRONTEND + "/#/assess"); await page.waitForTimeout(1500);
    const t = await page.locator("main").innerText(); need(/no trained model|No model is loaded|unavailable/i.test(t), "no explanation: " + t.slice(0, 200));
    need((await page.getByRole("button", { name: "Analyse motor" }).count()) === 0, "Analyse offered without a model");
    const lamp = (await page.locator("header [role=status]").first().innerText()).replace(/\n/g, " ");
    await page.goto(FRONTEND + "/#/upload"); await page.locator('input[type="file"]').setInputFiles(writeTmp("any.csv", csvOf([{ readings: SAMPLES.Normal[0].readings, motor: "X" }]))); await sleep(500);
    need(!(await page.getByRole("button", { name: "Analyse file" }).isEnabled()), "Analyse file enabled without a model");
    await shot(page, "FULL-UI-G"); need(dbCount() === before, "database changed");
    rec.actual(`header: '${lamp}'; New assessment: explanation without form; Upload: Analyse disabled; database unchanged`);
  });

  await scenario("UI-H", "H", "Database failure: the browser must not show a result or claim it was saved", {
    preconditions: "Backend restarted on the trained bundle; then the predictions table is dropped under the running server", input: "fill the form and press Analyse; then open History",
    expected: "'The assessment was not completed' + 'nothing is reported as saved'; no result banner; History shows an error with Try again; entries kept", corrective_action: "AssessPage error path / error handlers",
  }, async (page, rec) => {
    await startServer({ fresh: true });
    await submitForm(page, SAMPLES.Alert[0].readings, uid("UI-H0")); await readResult(page);                       // proves it works before the failure
    execFileSync(PY, [join(FULL, "harness.py"), "dropdb", "--db", DB], { cwd: FULL });
    await page.getByRole("button", { name: "Start a new assessment" }).click();
    await fillAssessment(page, { motor: uid("UI-H"), readings: Object.fromEntries(Object.entries(SAMPLES.Danger[0].readings).map(([k, v]) => [k, String(v)])) });
    await page.getByRole("button", { name: "Analyse motor" }).click();
    await page.getByText(/The assessment was not completed|The server did not accept/).waitFor({ timeout: 15000 });
    const t = await page.locator("main").innerText();
    need(/nothing is reported as saved/i.test(t), "no 'nothing saved' sentence"); need((await page.locator(".result-banner").count()) === 0, "a result is shown although it could not be saved");
    need(!/sqlite|OperationalError|no such table|Traceback/i.test(t), "technical database text leaked to the user");
    need((await page.locator('[data-testid="field-de_h_ge"]').inputValue()) !== "", "entries lost"); await shot(page, "FULL-UI-H");
    await page.goto(FRONTEND + "/#/history"); await page.getByText(/Could not load or export history|unavailable|could not/i).first().waitFor({ timeout: 10000 });
    rec.actual("after the table was dropped: message 'assessment was not completed … nothing is reported as saved', no result banner, no technical text, entries kept; History shows an error state");
  });

  await stopServer(); await closeBrowser();
  writeFileSync(join(OUT, "results_ui.json"), JSON.stringify({ results, meta: META }, null, 2));
  const bad = results.filter((r) => r.status !== "PASS"); console.log(`\nbrowser layer: ${results.length - bad.length}/${results.length} passed`);
  return bad.length;
}
if (process.argv[1] && process.argv[1].endsWith("suite_full.mjs")) runFull().then((n) => process.exit(n ? 1 : 0));
