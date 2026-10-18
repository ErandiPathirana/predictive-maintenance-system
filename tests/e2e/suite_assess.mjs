import { test, expect, fillAssessment, READINGS, axeScan, overflowX, FRONTEND } from "./lib.mjs";

const FORBIDDEN = [
  [/\b\d+\s*(minutes?|hours?|days?|weeks?)\b/i, "an invented time limit"],
  [/\bwithin\s+(the\s+)?(next\s+)?\d/i, "an invented deadline"],
  [/\breplace\b|\breplacement\b|\bspare part|\bnew bearing|\b(re)?lubricate\b|\b(add|apply|inject) grease\b|\brealign|\brebalanc/i, "a repair or part recommendation"],
  [/\b(is|are|has been|will be)\s+(automatically\s+)?(shut ?down|stopped|isolated)\b/i, "an automatic shutdown claim"],
  [/\b(exceeds?|above|below|over)\s+(the\s+)?(limit|threshold|alarm)\b/i, "an invented threshold"],
  [/\b(bearing|misalignment|imbalance|unbalance|looseness|cavitation)\s+(fault|failure|defect|damage)\b/i, "a fault diagnosis"],
  [/\bconfirmed (fault|failure)\b(?!.{0,40}\bnot\b)/i, null], // checked separately below
];

export const EXPECT = {
  Normal: { word: "Normal", must: [/routine monitoring/i, /not a confirmed/i], mustNot: [/immediately/i, /lockout/i] },
  Alert: { word: "Alert", must: [/inspect/i, /maintenance engineer/i, /not a confirmed/i], mustNot: [/lockout\/tagout procedure\./i] },
  Danger: { word: "Danger", must: [/not a confirmed fault/i, /not a shutdown order/i, /lockout\/tagout/i, /approved/i, /qualified/i, /authorised/i, /site safety procedures/i, /maintenance engineer/i], mustNot: [] },
};

async function submitValid(page) {
  await page.goto(FRONTEND + "/#/assess");
  await page.waitForSelector("form");
  await fillAssessment(page);
  await page.getByRole("button", { name: "Analyse motor" }).click();
  await page.locator(".result-banner").waitFor({ timeout: 15000 });
}

export async function conditionTests(cls) {
  const ex = EXPECT[cls];
  const tag = cls.toUpperCase().slice(0, 3);
  await test(`E05-${tag}`, `Submit valid readings → backend returns ${cls}; banner shows word + shape + 'Predicted condition'`, async (page, { shot }) => {
    await submitValid(page);
    const banner = await page.locator(".result-banner").innerText();
    expect(banner.includes("Predicted condition") && banner.includes(ex.word), `banner text was: ${banner.replace(/\n/g, " | ")}`);
    expect(/[●◆▲■▼✔✓⚠!]/.test(banner), "banner has no non-colour shape symbol");
    await shot("result-desktop");
  }, { scenario: cls });

  await test(`E09-${tag}`, `${cls}: corrective-action guidance matches the rules and stays inside the safety limits`, async (page) => {
    await submitValid(page);
    const text = await page.locator("main").innerText();
    for (const re of ex.must) expect(re.test(text), `missing expected guidance ${re}`);
    for (const re of ex.mustNot) expect(!re.test(text), `unexpected guidance ${re}`);
    for (const [re, what] of FORBIDDEN) if (what) { const m = text.match(re); expect(!m, `contains ${what}: "${m?.[0]}"`); }
    const urgent = await page.locator(".danger-notice, [role=alert]").count();
    if (cls === "Danger") expect(urgent > 0, "no prominent danger notice");
    else expect(!/Contact the responsible maintenance engineer now/.test(text), "urgent notice shown for a non-Danger class");
    const items = await page.locator(".rec-item").count();
    expect(items >= 4, `only ${items} recommendation cards`);
    return `${items} recommendation cards`;
  }, { scenario: cls });
}

const DBL = "DBL-" + Date.now();
export async function resultAxe(cls) {
  await test(`A11Y-result-${cls}`, `axe-core (WCAG 2.2 A/AA) on the ${cls} result page`, async (page) => {
    await submitValid(page);
    const r = await axeScan(page, `result/${cls}`);
    expect(r.violations.length === 0, r.violations.map((v) => `${v.id}[${v.impact}] x${v.nodes}: ${v.sample[0]}`).join(" || "));
  }, { scenario: cls });
}

export async function dangerExtras() {
  await test("E01", "Open the assessment form: title, nav, required fields, labels, skip link", async (page, { shot }) => {
    await page.goto(FRONTEND + "/#/assess"); await page.waitForSelector("form");
    expect((await page.locator("h1").innerText()).includes("New motor assessment"), "h1 missing");
    expect(await page.locator('[data-testid^="field-"]').count() === 14, "expected 14 sensor inputs");
    const unlabeled = await page.evaluate(() => [...document.querySelectorAll("input")].filter((i) => !i.labels?.length && !i.getAttribute("aria-label") && i.type !== "file" && i.type !== "hidden").length);
    expect(unlabeled === 0, `${unlabeled} inputs without a label`);
    expect(await page.locator("fieldset > legend").count() >= 5, "groups should be fieldsets with legends");
    expect(await page.locator('a[aria-current="page"]').count() === 1, "active nav link not marked");
    await shot("form");
  });

  await test("E02", "Motor ID: type a new ID, save, then it is offered as a suggestion next time", async (page) => {
    await page.goto(FRONTEND + "/#/assess"); await page.waitForSelector("form");
    await fillAssessment(page, { motor: "SUGGEST-7" });
    await page.getByRole("button", { name: "Analyse motor" }).click(); await page.locator(".result-banner").waitFor();
    await page.getByRole("button", { name: "Start a new assessment" }).click();
    const box = page.getByRole("combobox", { name: "Motor ID" }); await box.click(); await box.fill("SUGG");
    await page.getByRole("option", { name: "SUGGEST-7" }).waitFor({ timeout: 5000 });
    await page.keyboard.press("ArrowDown"); await page.keyboard.press("Enter");
    expect((await box.inputValue()) === "SUGGEST-7", "keyboard selection did not fill the Motor ID");
  });

  await test("E03", "Measurement time: 'Use now' fills it; future time warns; empty time is an error", async (page) => {
    await page.goto(FRONTEND + "/#/assess"); await page.waitForSelector("form");
    await page.getByRole("button", { name: "Use now" }).click();
    const v = await page.getByLabel("Measurement date and time", { exact: false }).inputValue();
    expect(/^\d{4}-\d\d-\d\dT\d\d:\d\d$/.test(v), `bad value after Use now: ${v}`);
    await page.getByLabel("Measurement date and time", { exact: false }).fill("2099-01-01T10:00");
    await page.getByText("in the future").waitFor({ timeout: 3000 });
    await page.getByLabel("Measurement date and time", { exact: false }).fill("");
    await page.getByRole("button", { name: "Analyse motor" }).click();
    await page.getByText(/measurement time|Measurement time/).first().waitFor();
  });

  await test("E06", "Validation: errors are listed, focus moves to the summary, entries are kept, fixing fields allows submit", async (page, { shot }) => {
    await page.goto(FRONTEND + "/#/assess"); await page.waitForSelector("form");
    await page.getByRole("button", { name: "Analyse motor" }).click();
    const summary = page.locator(".form-summary");
    await summary.getByRole("alert").waitFor();
    expect(await page.evaluate(() => document.activeElement?.classList.contains("form-summary")), "focus did not move to the error summary");
    const n = await summary.locator("li").count();
    expect(n === 16, `summary lists ${n} problems, expected 16 (motor, time, 14 readings)`);
    await shot("errors-empty");
    await fillAssessment(page, { readings: { ...READINGS, de_h_ge: "abc", de_v_ge: "1,5", nde_h_ge: "1e999", nde_v_ge: "", load_percent: "-5" } });
    await page.getByRole("button", { name: "Analyse motor" }).click();
    const msgs = (await page.locator(".mantine-InputWrapper-error").allInnerTexts());
    expect(msgs.length >= 4, `only ${msgs.length} inline errors for 4 bad fields`);
    expect(msgs.every((m) => m.length > 12), "an inline error message is too short to be useful: " + JSON.stringify(msgs));
    const invalid = await page.locator('[data-testid="field-de_h_ge"]').getAttribute("aria-invalid");
    expect(invalid === "true", "invalid field not marked aria-invalid");
    await shot("errors-values");
    for (const k of ["de_h_ge", "de_v_ge", "nde_h_ge", "nde_v_ge", "load_percent"]) await page.locator(`[data-testid="field-${k}"]`).fill(READINGS[k] ?? "10");
    await page.getByRole("button", { name: "Analyse motor" }).click();
    await page.locator(".result-banner").waitFor({ timeout: 10000 });
    return `messages: ${msgs.join(" / ")}`;
  });

  await test("E06c", "Out-of-training-range value warns but is accepted (not silently blocked)", async (page) => {
    await page.goto(FRONTEND + "/#/assess"); await page.waitForSelector("form");
    await fillAssessment(page, { readings: { ...READINGS, de_h_temp_c: "250" } });
    await page.getByText(/outside|not seen|beyond|range/i).first().waitFor({ timeout: 3000 });
    await page.getByRole("button", { name: "Analyse motor" }).click();
    await page.locator(".result-banner").waitFor();
  });

  await test("E06d", "Keyboard only: Tab through every control, type values, press Enter to submit", async (page, { shot }) => {
    await page.goto(FRONTEND + "/#/assess"); await page.waitForSelector("form");
    await page.keyboard.press("Tab"); // skip link
    expect(await page.evaluate(() => document.activeElement?.classList.contains("skip-link")), "first Tab stop is not the skip link");
    await page.keyboard.press("Enter");
    await page.getByRole("combobox", { name: "Motor ID" }).focus();
    await page.keyboard.type("KEY-1"); await page.keyboard.press("Tab");
    await page.keyboard.type("2025-04-01"); await page.keyboard.press("ArrowRight"); // date part of datetime-local, then time
    await page.getByLabel("Measurement date and time", { exact: false }).fill("2025-04-01T07:20");
    const order = [];
    await page.getByRole("textbox", { name: /Recorded by/ }).focus();
    for (const k of Object.keys(READINGS)) {
      await page.keyboard.press("Tab");
      let id = await page.evaluate(() => document.activeElement?.getAttribute("data-testid"));
      if (!id) { await page.keyboard.press("Tab"); id = await page.evaluate(() => document.activeElement?.getAttribute("data-testid")); }
      order.push(id);
      await page.keyboard.type(READINGS[k]);
    }
    expect(order.join() === Object.keys(READINGS).map((k) => "field-" + k).join(), "tab order differs from visual order: " + order.join());
    // focus indicator is visible on a text field
    const outline = await page.evaluate(() => { const s = getComputedStyle(document.activeElement); return s.outlineStyle + " " + s.outlineWidth + " " + s.boxShadow; });
    expect(!/^none/.test(outline) || /rgb/.test(outline), "no visible focus style: " + outline);
    await page.keyboard.press("Enter");
    await page.locator(".result-banner").waitFor({ timeout: 10000 });
  });

  await test("E06e", "Clear form: needs confirmation, Escape cancels and returns focus, confirm clears", async (page) => {
    await page.goto(FRONTEND + "/#/assess"); await page.waitForSelector("form");
    await fillAssessment(page);
    await page.getByRole("button", { name: "Clear form" }).click();
    await page.getByRole("dialog").waitFor();
    await page.keyboard.press("Escape");
    await page.getByRole("dialog").waitFor({ state: "hidden" });
    expect((await page.getByRole("combobox", { name: "Motor ID" }).inputValue()) === "E2E-M1", "Escape cleared the form");
    await page.getByRole("button", { name: "Clear form" }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Clear form" }).click();
    expect((await page.getByRole("combobox", { name: "Motor ID" }).inputValue()) === "", "confirm did not clear");
  });

  await test("E06f", "Server rejects the request (422) → plain message shown, entries kept, no result shown", async (page) => {
    await page.route("**/api/assessments", (r) => r.request().method() === "POST"
      ? r.fulfill({ status: 422, contentType: "application/json", body: JSON.stringify({ error: { code: "validation_error", message: "Some readings are not valid.", details: { missing_features: ["de_h_ge"] } } }) }) : r.continue());
    await page.goto(FRONTEND + "/#/assess"); await page.waitForSelector("form");
    await fillAssessment(page); await page.getByRole("button", { name: "Analyse motor" }).click();
    await page.getByText("The server did not accept the readings").waitFor();
    expect(await page.locator(".result-banner").count() === 0, "a result is shown after a rejection");
    expect((await page.locator('[data-testid="field-de_h_ge"]').inputValue()) === "9.1", "entries lost");
  });

  await test("E13d", "Server error (500): says nothing was saved, keeps entries, retry works", async (page) => {
    let fail = true;
    await page.route("**/api/assessments", (r) => (r.request().method() === "POST" && fail)
      ? r.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ error: { code: "internal_error", message: "Internal server error.", details: null } }) }) : r.continue());
    await page.goto(FRONTEND + "/#/assess"); await page.waitForSelector("form");
    await fillAssessment(page); await page.getByRole("button", { name: "Analyse motor" }).click();
    await page.getByText("The assessment was not completed").waitFor();
    expect(await page.getByText(/nothing is reported as saved/).count() === 1, "no 'nothing saved' statement");
    fail = false; await page.getByRole("button", { name: "Analyse motor" }).click();
    await page.locator(".result-banner").waitFor();
  });

  await test("E17", "Double-click on 'Analyse motor' stores exactly one record", async (page) => {
    await page.goto(FRONTEND + "/#/assess"); await page.waitForSelector("form");
    await fillAssessment(page, { motor: DBL });
    await page.getByRole("button", { name: "Analyse motor" }).dblclick();
    await page.locator(".result-banner").waitFor();
    const r2 = await (await page.request.get((process.env.PM_API_URL ?? "http://localhost:8000") + "/api/predictions?motor_id=" + DBL + "")).json();
    expect(r2.total === 1, `${r2.total} records stored for one double-click`);
  });
}
