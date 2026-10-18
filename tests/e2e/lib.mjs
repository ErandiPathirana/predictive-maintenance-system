// Tiny test harness: every test gets a fresh browser context, failures are recorded (not thrown), screenshots go to ./evidence.
import { chromium } from "playwright";
import { createRequire } from "node:module";
import { mkdirSync, writeFileSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

export const HERE = dirname(fileURLToPath(import.meta.url));
export const EVIDENCE = join(HERE, "evidence");
export const FRONTEND = process.env.PM_FRONTEND_URL ?? "http://localhost:5173";
export const API = process.env.PM_API_URL ?? "http://localhost:8000";
export const VIEWPORTS = { desktop: { width: 1280, height: 900 }, tablet: { width: 768, height: 1024 }, mobile: { width: 375, height: 800 } };
const AXE = readFileSync(createRequire(import.meta.url).resolve("axe-core/axe.min.js"), "utf8");
mkdirSync(EVIDENCE, { recursive: true });

export const results = [];
let browser;
export async function launch() {
  browser = await chromium.launch({ executablePath: process.env.PM_CHROMIUM ?? undefined, args: ["--no-sandbox"] });
  return browser;
}
export const closeBrowser = () => browser?.close();

export function expect(cond, msg) { if (!cond) throw new Error(msg); }

/** Runs one test. fn(page, ctx) may throw. Console errors from the page are collected and reported as notes. */
export async function test(id, title, fn, { viewport = "desktop", scenario = "", keepOffline = false } = {}) {
  const context = await browser.newContext({ viewport: VIEWPORTS[viewport], acceptDownloads: true });
  const page = await context.newPage();
  const consoleErrors = [];
  page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text().slice(0, 160)); });
  page.on("pageerror", (e) => consoleErrors.push("PAGEERROR " + String(e).slice(0, 160)));
  const r = { id, title, scenario, viewport, status: "PASS", note: "", consoleErrors };
  try { const out = (await fn(page, { shot: (n) => shot(page, `${id}-${n}`) })) ?? ""; if (typeof out === "object") { r.status = out.status; r.note = out.note; } else r.note = out; }
  catch (e) { r.status = "FAIL"; r.note = String(e.message ?? e).split("\n")[0].slice(0, 400); try { await shot(page, `${id}-FAIL`); } catch {} }
  await context.close();
  results.push(r);
  console.log(`${r.status.padEnd(4)} ${id} ${title}${r.note ? "  -- " + r.note : ""}`);
  return r;
}
export const shot = (page, name) => page.screenshot({ path: join(EVIDENCE, name + ".png"), fullPage: true });

export const READINGS = { de_h_velocity_mm_s: "8.2", de_h_ge: "9.1", de_h_temp_c: "10.5", de_v_velocity_mm_s: "7.9", de_v_ge: "8.8", de_v_temp_c: "10.2",
  nde_h_velocity_mm_s: "8.0", nde_h_ge: "9.3", nde_h_temp_c: "10.8", nde_v_velocity_mm_s: "7.7", nde_v_ge: "8.6", nde_v_temp_c: "10.1", rotational_speed_rpm: "10", load_percent: "10" };

export async function fillAssessment(page, { motor = "E2E-M1", when = "2025-04-01T07:20", readings = READINGS } = {}) {
  await page.getByRole("combobox", { name: "Motor ID" }).fill(motor);
  await page.getByLabel("Measurement date and time", { exact: false }).fill(when);
  for (const [k, v] of Object.entries(readings)) await page.locator(`[data-testid="field-${k}"]`).fill(v);
}

export async function axeScan(page, label) {
  await page.evaluate(AXE);
  const res = await page.evaluate(async () => (await window.axe.run(document, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"] } })).violations
    .map((v) => ({ id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.length, sample: v.nodes.slice(0, 3).map((n) => n.target.join(" ") + " :: " + (n.any[0]?.message ?? n.all[0]?.message ?? n.none[0]?.message ?? "").slice(0, 140)) })));
  return { label, violations: res };
}

export async function overflowX(page) {
  return page.evaluate(() => ({ doc: document.documentElement.scrollWidth, win: window.innerWidth }));
}

export function writeResults(file) { writeFileSync(join(HERE, file), JSON.stringify(results, null, 2)); }

import { spawn } from "node:child_process";
/** Starts tests/e2e/start_backend.py. Resolves when /api/health answers (or when the port answers for 'none'). */
export async function startBackend(cond, { delay = 0, port = 8000 } = {}) {
  const py = process.env.PM_PYTHON ?? "python";
  const args = [join(HERE, "start_backend.py"), cond, "--port", String(port), ...(delay ? ["--delay", String(delay)] : [])];
  const proc = spawn(py, args, { stdio: ["ignore", "pipe", "pipe"] });
  let log = ""; proc.stdout.on("data", (d) => (log += d)); proc.stderr.on("data", (d) => (log += d));
  const t0 = Date.now();
  for (;;) {
    if (proc.exitCode !== null) throw new Error(`backend exited (${proc.exitCode}): ${log.slice(-400)}`);
    try { const r = await fetch(`http://127.0.0.1:${port}/api/health`); if (r.status < 500 || cond === "none") break; } catch {}
    if (Date.now() - t0 > 30000) { proc.kill(); throw new Error("backend did not start: " + log.slice(-400)); }
    await new Promise((r) => setTimeout(r, 250));
  }
  return { stop: () => new Promise((res) => { proc.once("exit", res); proc.kill("SIGTERM"); setTimeout(res, 3000); }) };
}
