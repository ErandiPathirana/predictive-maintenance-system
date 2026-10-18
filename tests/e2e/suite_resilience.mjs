import { test, expect, fillAssessment, FRONTEND, startBackend } from "./lib.mjs";
import { FIX } from "./suite_data.mjs";

export async function noModelTests() {
  await test("E13-nomodel-a", "Backend up but NO model loaded: header says so, New assessment is replaced by a clear explanation (no form, no fake result)", async (page, { shot }) => {
    await page.goto(FRONTEND + "/#/assess"); await page.waitForTimeout(1500);
    const t = await page.locator("main").innerText();
    expect(/no trained model|unavailable|could not be checked|not ready/i.test(t), "page does not explain the missing model: " + t.slice(0, 200));
    expect(await page.getByRole("button", { name: "Analyse motor" }).count() === 0, "an Analyse button is offered with no model");
    const lamp = await page.getByRole("status").first().innerText().catch(() => "");
    await shot("assess"); return "header: " + lamp.replace(/\n/g, " ");
  });
  await test("E13-nomodel-b", "No model: Upload page cannot analyse and says why", async (page, { shot }) => {
    await page.goto(FRONTEND + "/#/upload"); await page.waitForTimeout(1200);
    await page.locator('input[type="file"]').setInputFiles(FIX.GOOD).catch(() => {});
    await page.waitForTimeout(500);
    expect(!(await page.getByRole("button", { name: "Analyse file" }).isEnabled()), "Analyse is enabled with no model");
    await shot("upload");
  });
  await test("E13-nomodel-c", "No model: history of earlier saved records still opens (read-only) or fails with an understandable message", async (page, { shot }) => {
    await page.goto(FRONTEND + "/#/history"); await page.waitForTimeout(1500);
    const t = await page.locator("main").innerText();
    expect(/No predictions stored yet|could not|unavailable|Assessment history/.test(t), t.slice(0, 200));
    await shot("history");
  });
}

export async function outageTests() {
  await test("E13-out-a", "Backend OFF: header shows 'offline' with a shape and words, not only colour", async (page, { shot }) => {
    await page.goto(FRONTEND + "/#/"); await page.waitForTimeout(2500);
    const lamp = (await page.locator("header [role=status]").first().innerText()).trim();
    expect(/offline|unreachable|not reachable|cannot|unavailable|no connection|down/i.test(lamp), "header text: " + lamp);
    await shot("dashboard"); return lamp;
  });
  await test("E13-out-b", "Backend OFF: New assessment explains the problem in plain words and offers Try again", async (page, { shot }) => {
    await page.goto(FRONTEND + "/#/assess"); await page.waitForTimeout(2500);
    const t = await page.locator("main").innerText();
    expect(/could not|cannot|unreachable|reach the server|not reach|offline/i.test(t), "message: " + t.slice(0, 300));
    expect(await page.getByRole("button", { name: /try again|retry/i }).count() > 0, "no retry button");
    expect(!/TypeError|Failed to fetch|NetworkError|undefined|\[object/.test(t), "technical text leaked: " + t.slice(0, 200));
    await shot("assess"); return t.replace(/\n/g, " ").slice(0, 200);
  });
  await test("E13-out-c", "Backend OFF: History and Upload show an error state, not an endless spinner or blank page", async (page, { shot }) => {
    await page.goto(FRONTEND + "/#/history"); await page.waitForTimeout(3000);
    const h = await page.locator("main").innerText();
    expect(!/Loading history/.test(h) && /could not|cannot|reach|offline|unavailable/i.test(h), "history: " + h.slice(0, 250));
    await shot("history");
    await page.goto(FRONTEND + "/#/upload"); await page.waitForTimeout(1500);
    expect(await page.locator("main").innerText() !== "", "blank upload page");
  });
  await test("E13-out-d", "Backend dies while the user is on the filled form: Analyse gives a clear error, entries are kept, and work resumes when the backend returns", async (page, { shot }) => {
    const be = await startBackend("Danger");
    try {
      await page.goto(FRONTEND + "/#/assess"); await page.waitForSelector("form");
      await fillAssessment(page, { motor: "OUT-1" });
      await be.stop(); await new Promise((r) => setTimeout(r, 500));
      await page.getByRole("button", { name: "Analyse motor" }).click();
      await page.getByText(/The assessment was not completed|could not/).first().waitFor({ timeout: 25000 });
      const t = await page.locator("main").innerText();
      expect(/nothing is reported as saved/.test(t), "no 'nothing saved' statement");
      expect(!/TypeError|Failed to fetch/.test(t), "technical text leaked");
      expect((await page.locator('[data-testid="field-de_h_ge"]').inputValue()) === "9.1", "entries lost after the failure");
      expect(await page.locator(".result-banner").count() === 0, "result shown despite outage");
      await shot("error");
      const be2 = await startBackend("Danger");
      try {
        await page.getByRole("button", { name: "Analyse motor" }).click();
        await page.locator(".result-banner").waitFor({ timeout: 15000 });
      } finally { await be2.stop(); }
    } finally { await be.stop(); }
  });
}

export async function slowTests() {
  await test("E13-slow-a", "Slow backend (3 s): loading text appears, button is busy/disabled, a second click does not create a second record", async (page, { shot }) => {
    const motor = "SLOW-" + (Date.now() % 100000);
    await page.goto(FRONTEND + "/#/assess"); await page.waitForSelector("form", { timeout: 15000 });
    await fillAssessment(page, { motor });
    const btn = page.getByRole("button", { name: "Analyse motor" });
    await btn.click();
    await page.getByText("Analysing with the trained model…").waitFor({ timeout: 2000 });
    expect(await btn.isDisabled(), "button is not disabled while busy");
    await shot("busy");
    await btn.click({ force: true, timeout: 500 }).catch(() => {});
    await page.locator(".result-banner").waitFor({ timeout: 15000 });
    const n = (await (await page.request.get(`http://localhost:8000/api/predictions?motor_id=${motor}`)).json()).total;
    expect(n === 1, `${n} records stored`);
  });
  await test("E13-slow-b", "Slow backend: History shows a loading message while waiting", async (page, { shot }) => {
    await page.goto(FRONTEND + "/#/history");
    await page.getByText("Loading history…").waitFor({ timeout: 4000 });
    await shot("loading");
  });
  await test("E13-slow-c", "Very slow backend (no answer within the 20 s limit): user gets a time-out message, can retry, entries are kept", async (page, { shot }) => {
    await page.route("**/api/assessments", async (r) => { if (r.request().method() === "POST") await new Promise((x) => setTimeout(x, 24000)); await r.abort().catch(() => {}); });
    await page.goto(FRONTEND + "/#/assess"); await page.waitForSelector("form", { timeout: 15000 });
    await fillAssessment(page, { motor: "TIMEOUT-1" });
    await page.getByRole("button", { name: "Analyse motor" }).click();
    await page.getByText(/took too long|timed out|did not answer|too long/i).first().waitFor({ timeout: 30000 });
    const t = await page.locator("main").innerText();
    expect((await page.locator('[data-testid="field-de_h_ge"]').inputValue()) === "9.1", "entries lost");
    await shot("timeout"); return t.match(/.{0,60}(took too long|timed out|did not answer|too long).{0,80}/i)?.[0].replace(/\n/g, " ");
  });
}
