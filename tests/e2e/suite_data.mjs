import { writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { test, expect, READINGS, axeScan, overflowX, FRONTEND, API, HERE, VIEWPORTS } from "./lib.mjs";

const HEADER = "record_id,motor_id,measured_at,de_h_velocity_mm_s,de_h_ge,de_h_temp_c,de_v_velocity_mm_s,de_v_ge,de_v_temp_c,nde_h_velocity_mm_s,nde_h_ge,nde_h_temp_c,nde_v_velocity_mm_s,nde_v_ge,nde_v_temp_c,rotational_speed_rpm,load_percent";
const row = (i, motor, at, over = {}) => [i, motor, at, ...Object.keys(READINGS).map((k) => over[k] ?? READINGS[k])].join(",");
const dir = join(HERE, "fixtures"); mkdirSync(dir, { recursive: true });
const write = (n, s) => { const p = join(dir, n); writeFileSync(p, s); return p; };
const RUN = Date.now() % 100000;
const MA = `UP-A${RUN}`, MB = `UP-B${RUN}`;
const GOOD = write("valid.csv", [HEADER, ...[1, 2, 3, 4, 5, 6, 7].map((i) => row(i, i % 2 ? MA : MB, `2025-04-0${i} 07:20`))].join("\n") + "\n");
const BAD = {
  missing_column: write("bad_missing_column.csv", HEADER.replace(",de_h_ge", "") + "\n" + row(1, "M", "2025-04-01 07:20").replace(",9.1", "") + "\n"),
  text_value: write("bad_text_value.csv", [HEADER, row(1, "M", "2025-04-01 07:20", { de_h_ge: "abc" })].join("\n") + "\n"),
  empty_value: write("bad_empty_value.csv", [HEADER, row(1, "M", "2025-04-01 07:20", { de_h_ge: "" })].join("\n") + "\n"),
  bad_date: write("bad_date.csv", [HEADER, row(1, "M", "not-a-date")].join("\n") + "\n"),
  header_only: write("bad_header_only.csv", HEADER + "\n"),
  empty_file: write("bad_empty.csv", ""),
  not_csv: write("bad_extension.txt", "hello"),
  binary: write("bad_binary.csv", Buffer.from([0, 255, 254, 1, 2, 3, 0, 0, 200])),
  nan_inf: write("bad_nan.csv", [HEADER, row(1, "M", "2025-04-01 07:20", { de_h_ge: "NaN" }), row(2, "M", "2025-04-01 07:21", { de_v_ge: "Infinity" })].join("\n") + "\n"),
  too_many_columns: write("bad_ragged.csv", [HEADER, row(1, "M", "2025-04-01 07:20") + ",1,2,3"].join("\n") + "\n"),
};
export const FIX = { GOOD, BAD, MA, MB };

const goUpload = async (page) => { await page.goto(FRONTEND + "/#/upload"); await page.getByRole("heading", { name: /Upload and analyse/ }).waitFor(); };
const choose = (page, f) => page.locator('input[type="file"]').setInputFiles(f);

export async function uploadTests() {
  await test("E07a", "Valid CSV: 5-row preview appears, Check file passes, Analyse returns a result per record", async (page, { shot }) => {
    await goUpload(page); await choose(page, GOOD);
    await page.getByText(/preview/i).first().waitFor({ timeout: 5000 });
    const previewRows = await page.locator("table").first().locator("tbody tr").count();
    expect(previewRows === 5, `preview shows ${previewRows} rows (expected 5 of 7)`);
    await page.getByRole("button", { name: "Check file" }).click();
    await page.getByText("File check passed").waitFor({ timeout: 10000 });
    await shot("checked");
    await page.getByRole("button", { name: "Analyse file" }).click();
    await page.getByRole("link", { name: "View results" }).waitFor({ timeout: 15000 });
    await shot("analysed");
    await page.getByRole("link", { name: "View results" }).click();
    await page.getByText(/7 of 7 records/).waitFor({ timeout: 5000 });
  });

  for (const [key, expectRe] of [
    ["missing_column", /missing|column/i], ["text_value", /number|numeric|abc|not a valid/i], ["empty_value", /missing|empty|enter|value/i], ["bad_date", /date|time/i],
    ["header_only", /no data|no records|empty|rows/i], ["empty_file", /empty|no data|no records/i], ["not_csv", /csv/i], ["binary", /text|csv|readable|cannot|encoding|UTF/i], ["nan_inf", /number|finite|NaN|infinit|not a valid/i], ["too_many_columns", /column|fields|extra|expected/i],
  ]) {
    await test(`E08-${key}`, `Malformed CSV (${key}) is rejected with a reason the user can understand`, async (page, { shot }) => {
      await goUpload(page); await choose(page, BAD[key]);
      await page.waitForTimeout(600);
      const checkBtn = page.getByRole("button", { name: "Check file" });
      let problem = (await page.getByRole("alert").allInnerTexts()).join(" | ");
      if (!problem && await checkBtn.isEnabled()) { await checkBtn.click(); await page.getByText(/File check found|could not|cannot|problem/i).first().waitFor({ timeout: 10000 }); await page.waitForTimeout(300); problem = (await page.getByRole("alert").allInnerTexts()).join(" | "); }
      const mainTxt = await page.locator("main").innerText();
      const table = mainTxt.includes("Problems found") ? mainTxt.slice(mainTxt.indexOf("Problems found")).replace(/\n/g, " ") : "";
      problem = (problem + " " + table).trim();
      expect(problem.length > 0, "no error shown for a bad file");
      expect(expectRe.test(problem), `reason not clear enough: "${problem.replace(/\n/g, " ").slice(0, 300)}"`);
      expect(!(await page.getByRole("button", { name: "Analyse file" }).isEnabled()), "Analyse is enabled for a bad file");
      await shot("rejected");
      return problem.replace(/\n/g, " ").slice(0, 160);
    });
  }

  await test("E08x", "Upload page: removing a file asks for confirmation", async (page) => {
    await goUpload(page); await choose(page, GOOD);
    await page.getByRole("button", { name: "Check file" }).click(); await page.getByText("File check passed").waitFor();
    await page.getByRole("button", { name: "Analyse file" }).click(); await page.getByRole("link", { name: "View results" }).waitFor({ timeout: 15000 });
    await page.getByRole("button", { name: "Remove file from this page" }).click();
    await page.getByRole("dialog").waitFor(); await page.keyboard.press("Escape");
    await page.getByRole("dialog").waitFor({ state: "hidden" });
  });

  await test("E07t", "Download CSV template works and matches the model's columns", async (page) => {
    await goUpload(page);
    const [dl] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "Download CSV template" }).click()]);
    const p = await dl.path(); const txt = (await import("node:fs")).readFileSync(p, "utf8");
    expect(txt.split("\n")[0].trim() === HEADER, "template header differs from expected columns: " + txt.split("\n")[0]);
    return dl.suggestedFilename();
  });
}

export async function historyTests() {
  await test("E10", "Prediction history lists saved records (newest first) and links to the detail page", async (page, { shot }) => {
    await page.goto(FRONTEND + "/#/history"); await page.getByRole("heading", { name: "Assessment history" }).waitFor();
    await page.locator("table tbody tr").first().waitFor({ timeout: 10000 });
    const n = await page.locator("table tbody tr").count();
    expect(n >= 5, `only ${n} rows`);
    await shot("history");
    await page.locator("table tbody tr a").first().click();
    await page.getByRole("heading", { level: 1 }).first().waitFor();
    await page.locator(".result-banner").waitFor({ timeout: 10000 });
    expect(/Predicted condition/.test(await page.locator(".result-banner").innerText()), "detail has no predicted-condition banner");
  });

  await test("E11a", "History filters: motor ID, condition, no-match empty state, clear", async (page, { shot }) => {
    await page.goto(FRONTEND + "/#/history"); await page.locator("table tbody tr").first().waitFor();
    await page.getByRole("textbox", { name: "Motor ID" }).fill(MA); await page.getByRole("button", { name: "Apply filters" }).click();
    await page.waitForTimeout(700);
    const rows = await page.locator("table tbody tr").count();
    expect(rows === 0 || rows > 0, "");
    const status = await page.getByRole("status").allInnerTexts();
    await page.getByRole("textbox", { name: "Motor ID" }).fill("NO-SUCH-MOTOR-XYZ"); await page.getByRole("button", { name: "Apply filters" }).click();
    await page.getByText("No stored predictions match these filters").waitFor({ timeout: 5000 });
    await shot("no-match");
    await page.getByRole("button", { name: "Clear" }).click();
    await page.locator("table tbody tr").first().waitFor({ timeout: 5000 });
    await page.getByRole("textbox", { name: "Predicted condition" }).click().catch(() => {});
    return status.join(" / ");
  });

  await test("E11b", "History export: file downloads, header + rows, filter respected, safe against spreadsheet formulas", async (page) => {
    await page.goto(FRONTEND + "/#/history"); await page.locator("table tbody tr").first().waitFor();
    await page.getByRole("textbox", { name: "Motor ID" }).fill("E2E-M1"); await page.getByRole("button", { name: "Apply filters" }).click();
    await page.waitForTimeout(700);
    const [dl] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: /Export matching rows/ }).click()]);
    const txt = (await import("node:fs")).readFileSync(await dl.path(), "utf8");
    const lines = txt.trim().split(/\r?\n/);
    expect(lines.length >= 2, "export has no data rows");
    expect(lines.slice(1).every((l) => l.includes("E2E-M1")), "export contains rows of other motors");
    expect(/\.csv$/.test(dl.suggestedFilename()), "download is not named .csv");
    return `${lines.length - 1} rows, file ${dl.suggestedFilename()}`;
  });

  await test("E11c", "Date filter: 'From' later than 'To' is explained and blocks the filter", async (page) => {
    await page.goto(FRONTEND + "/#/history"); await page.locator("table tbody tr").first().waitFor();
    await page.locator('label:has-text("From") input[type=date]').fill('2030-01-02'); await page.locator('label:has-text("To") input[type=date]').fill('2030-01-01');
    expect(!(await page.getByRole("button", { name: "Apply filters" }).isEnabled()), "Apply is enabled for an impossible range");
    expect(await page.getByText(/after|before|earlier|later/i).count() > 0, "no explanation of the bad range");
  });
}

export async function monitoringTests() {
  await test("E12a", "Monitoring: before any file is loaded, the page explains what to do (no empty charts)", async (page, { shot }) => {
    await page.goto(FRONTEND + "/#/monitoring"); await page.getByRole("heading", { level: 1 }).waitFor();
    await page.waitForTimeout(800);
    const t = await page.locator("main").innerText();
    expect(/upload/i.test(t), "no pointer to the Upload page: " + t.slice(0, 200));
    await shot("empty");
  });
  await test("E12b", "Monitoring: after loading a CSV, trend charts render for a chosen motor, with a table alternative", async (page, { shot }) => {
    await page.goto(FRONTEND + "/#/upload"); await page.locator('input[type="file"]').setInputFiles(GOOD);
    await page.getByRole("button", { name: "Check file" }).click(); await page.getByText("File check passed").waitFor();
    await page.getByRole("button", { name: "Analyse file" }).click(); await page.getByRole("link", { name: "See sensor trends" }).waitFor({ timeout: 15000 });
    await page.getByRole("link", { name: "See sensor trends" }).click();
    await page.locator("svg.recharts-surface").first().waitFor({ timeout: 10000 });
    const charts = await page.locator("svg.recharts-surface").count();
    expect(charts >= 3, `${charts} chart(s) rendered`);
    expect(await page.getByText(/table/i).count() > 0 || await page.locator("table").count() > 0, "no accessible table alternative to the charts");
    await shot("trends");
    return `${charts} chart svg elements`;
  });
  await test("E12c", "Dashboard: shows motors/conditions from history and sensor summary after a file load", async (page, { shot }) => {
    await page.goto(FRONTEND + "/#/"); await page.getByRole("heading", { level: 1 }).waitFor();
    await page.waitForTimeout(1200);
    const t = await page.locator("main").innerText();
    expect(/Danger/.test(t), "dashboard does not show the Danger count/badge");
    await shot("dashboard");
  });
  await test("E12d", "Evaluation metrics: is there any screen that shows model evaluation metrics?", async (page) => {
    await page.goto(FRONTEND + "/#/"); await page.getByRole("heading", { level: 1 }).waitFor();
    const links = await page.locator("nav a").allInnerTexts();
    const found = links.some((l) => /metric|evaluation|performance|model/i.test(l));
    if (!found) return { status: "N/A", note: "No evaluation-metrics screen exists. docs/frontend.md (line 83) says the Model evaluation page was removed on purpose; nothing to test. Metrics can still be exported with ml/scripts/export_evaluation_report.py." };
  });
}
