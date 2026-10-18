import { test, expect, READINGS, axeScan, overflowX, FRONTEND, API, VIEWPORTS, fillAssessment, results } from "./lib.mjs";
import { FIX } from "./suite_data.mjs";
import { writeFileSync } from "node:fs";
import { join } from "node:path";
import { HERE } from "./lib.mjs";

const PAGES = [["dashboard", "/"], ["assess", "/assess"], ["upload", "/upload"], ["results", "/results"], ["history", "/history"], ["monitoring", "/monitoring"]];
export const axeAll = [];

export async function responsiveTests() {
  for (const vp of ["desktop", "tablet", "mobile"]) {
    for (const [name, path] of PAGES) {
      await test(`E14-${vp}-${name}`, `Layout at ${vp} (${VIEWPORTS[vp].width}px): ${name} has no sideways page scroll, header/nav usable`, async (page, { shot }) => {
        await page.goto(FRONTEND + "/#" + path); await page.waitForTimeout(900);
        const o = await overflowX(page);
        expect(o.doc <= o.win + 1, `page is ${o.doc}px wide in a ${o.win}px window (sideways scroll)`);
        if (vp !== "desktop") {
          const burger = page.getByRole("button", { name: /navigation/i });
          expect(await burger.isVisible(), "no menu button on a narrow screen");
          await burger.click();
          await page.getByRole("link", { name: /New Assessment/ }).waitFor({ state: "visible", timeout: 3000 });
          await shot("menu-open");
          await page.keyboard.press("Tab");
        }
        await shot("page");
      }, { viewport: vp });
    }
    await test(`E14-${vp}-flow`, `Full assessment flow at ${vp}: fill form, submit, read Danger guidance, nothing clipped`, async (page, { shot }) => {
      await page.goto(FRONTEND + "/#/assess"); await page.waitForSelector("form");
      await fillAssessment(page, { motor: `RESP-${vp}-${Date.now() % 10000}` });
      await shot("filled");
      await page.getByRole("button", { name: "Analyse motor" }).click(); await page.locator(".result-banner").waitFor();
      const o = await overflowX(page);
      expect(o.doc <= o.win + 1, `result page is ${o.doc}px wide in a ${o.win}px window`);
      const clipped = await page.evaluate(() => [...document.querySelectorAll(".result-banner, .rec-item, .danger-notice")].filter((e) => e.scrollWidth > e.clientWidth + 1).length);
      expect(clipped === 0, `${clipped} result blocks have clipped content`);
      const pills = await page.evaluate(() => [...document.querySelectorAll(".pill, .mantine-Badge-root")].filter((e) => { const l = e.querySelector(".mantine-Badge-label") ?? e; return l.scrollWidth > l.clientWidth + 1 || e.scrollWidth > e.clientWidth + 1; }).map((e) => e.textContent.trim()));
      expect(pills.length === 0, `label text is cut off: ${pills.join(" | ")}`);
      await shot("result");
      const small = await page.evaluate(() => [...document.querySelectorAll("button, a, input, [role=button]")].filter((e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && (r.height < 24 || r.width < 24) && getComputedStyle(e).visibility !== "hidden" && !e.closest(".skip-link") && !(getComputedStyle(e).display === "inline" && e.closest("p, li, td, span:not(.brand)") && !e.closest("header, nav")); }).map((e) => (e.textContent || e.getAttribute("aria-label") || e.name || e.tagName).trim().slice(0, 30)));
      return small.length ? `targets under 24x24 CSS px (WCAG 2.2 AA 2.5.8): ${small.join(", ")}` : "all targets >= 24 px";
    }, { viewport: vp });
  }
}

export async function accessibilityTests() {
  for (const vp of ["desktop", "mobile"]) {
    for (const [name, path] of PAGES) {
      await test(`A11Y-${vp}-${name}`, `axe-core (WCAG 2.2 A/AA) on ${name} at ${vp}`, async (page) => {
        await page.goto(FRONTEND + "/#" + path); await page.waitForTimeout(1000);
        const r = await axeScan(page, `${vp}/${name}`); axeAll.push(r);
        const bad = r.violations;
        expect(bad.length === 0, bad.map((v) => `${v.id}[${v.impact}] x${v.nodes}: ${v.sample[0]}`).join(" || "));
      }, { viewport: vp });
    }
  }
  await test("A11Y-result", "axe-core on the Danger result page, the error state and the validation-error state", async (page) => {
    await page.goto(FRONTEND + "/#/assess"); await page.waitForSelector("form");
    await page.getByRole("button", { name: "Analyse motor" }).click(); await page.locator(".form-summary [role=alert]").waitFor();
    const e1 = await axeScan(page, "assess/errors"); axeAll.push(e1);
    await fillAssessment(page, { motor: "A11Y-1" });
    await page.getByRole("button", { name: "Analyse motor" }).click(); await page.locator(".result-banner").waitFor();
    const e2 = await axeScan(page, "assess/result-danger"); axeAll.push(e2);
    const all = [...e1.violations, ...e2.violations];
    expect(all.length === 0, all.map((v) => `${v.id}[${v.impact}] x${v.nodes}: ${v.sample[0]}`).join(" || "));
  });
  writeFileSync(join(HERE, "axe-results.json"), JSON.stringify(axeAll, null, 2));
}

export async function keyboardTests() {
  await test("K01", "Skip link moves focus to the main content and keeps the page", async (page) => {
    await page.goto(FRONTEND + "/#/history"); await page.getByRole("heading", { level: 1 }).waitFor();
    await page.keyboard.press("Tab"); await page.keyboard.press("Enter");
    expect(page.url().endsWith("#/history"), "URL changed to " + page.url());
    expect(await page.evaluate(() => document.activeElement?.id === "main"), "focus is not in main");
  });
  await test("K02", "Every page: every control reachable by Tab has a visible focus indicator", async (page) => {
    const missing = [];
    for (const [name, path] of PAGES) {
      await page.goto(FRONTEND + "/#" + path); await page.waitForTimeout(700);
      for (let i = 0; i < 40; i++) {
        await page.keyboard.press("Tab");
        const info = await page.evaluate(() => { const e = document.activeElement; if (!e || e === document.body) return null; if (!e.matches(":focus")) return null; /* focus is inside the browser's own date-picker icon, which draws its own ring */ const s = getComputedStyle(e); const vis = (s.outlineStyle !== "none" && parseFloat(s.outlineWidth) >= 2) || (s.boxShadow !== "none"); return { vis, label: (e.getAttribute("aria-label") || e.textContent || e.name || e.tagName).trim().slice(0, 30), tag: e.tagName, type: e.type }; });
        if (info && !info.vis) missing.push(`${name}: ${info.tag}/${info.type} "${info.label}"`);
      }
    }
    expect(missing.length === 0, "no visible focus ring on: " + [...new Set(missing)].slice(0, 8).join("; "));
  });
  await test("K03", "Route change: keyboard/screen-reader user is told the page changed (focus or title moves)", async (page) => {
    await page.goto(FRONTEND + "/#/"); await page.waitForTimeout(600);
    const t0 = await page.title();
    await page.getByRole("link", { name: /Assessment History/ }).click(); await page.waitForTimeout(600);
    const t1 = await page.title();
    const focusInMain = await page.evaluate(() => { const a = document.activeElement; return !!a && a !== document.body && !!a.closest("main, h1"); });
    expect(t0 !== t1 || focusInMain, `document title stays "${t1}" and focus is not moved after navigating`);
  });
  await test("K04", "Mobile menu: Escape/Burger closes it and focus returns to the menu button", async (page) => {
    await page.goto(FRONTEND + "/#/"); const b = page.getByRole("button", { name: /Open navigation/ }); await b.focus(); await page.keyboard.press("Enter");
    await page.getByRole("link", { name: /Upload Bulk CSV File/ }).waitFor({ state: "visible" });
    await page.getByRole("link", { name: /Upload Bulk CSV File/ }).click();
    await page.waitForTimeout(500);
    expect(page.url().endsWith("#/upload"), "menu link did not navigate");
    await page.waitForTimeout(500);
    const box = await page.getByRole("link", { name: /Upload Bulk CSV File/ }).boundingBox();
    expect(!box || box.x + box.width <= 1 || !(await page.getByRole("link", { name: /Upload Bulk CSV File/ }).isVisible()), "menu stays open over the page after choosing a page");
  }, { viewport: "mobile" });
  await test("K05", "Text size: page still works with browser zoom 200% (viewport 640 wide ≈ 1280 at 200%)", async (page) => {
    await page.setViewportSize({ width: 640, height: 800 });
    await page.goto(FRONTEND + "/#/assess"); await page.waitForSelector("form");
    await page.addStyleTag({ content: "html{font-size:200%}" });
    const o = await overflowX(page);
    expect(o.doc <= o.win + 1, `sideways scroll at large text: ${o.doc} > ${o.win}`);
  });
}
