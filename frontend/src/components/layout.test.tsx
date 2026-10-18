import { fireEvent, screen, waitFor } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { theme } from "../theme";
import { mockApi, renderApp } from "../test/helpers";
import { AppLayout, titleFor } from "./AppLayout";

// Regression tests for defects found by the browser QA (docs/frontend-qa-report.md).

const ui = (
  <Routes>
    <Route element={<AppLayout />}>
      <Route index element={<h1>Home page</h1>} />
      <Route path="history" element={<h1>History page</h1>} />
    </Route>
  </Routes>
);

describe("Skip link (F1)", () => {
  it("moves focus to the main content and does not change the URL hash (HashRouter would read '#main' as a route)", async () => {
    mockApi({});
    renderApp(ui);
    const link = await screen.findByRole("link", { name: "Skip to main content" });
    const notPrevented = fireEvent.click(link);
    expect(notPrevented, "the click must be cancelled so the browser does not set location.hash").toBe(false);
    expect(document.activeElement?.id).toBe("main");
  });
});

describe("Page titles (F4)", () => {
  it("every menu page and the detail page have their own title", () => {
    expect(titleFor("/")).toBe("Dashboard - Motor condition monitor");
    expect(titleFor("/assess")).toBe("New assessment - Motor condition monitor");
    expect(titleFor("/history")).toBe("Assessment history - Motor condition monitor");
    expect(titleFor("/assessment/12")).toBe("Assessment details - Motor condition monitor");
    expect(titleFor("/nope")).toBe("Page not found - Motor condition monitor");
  });

  it("updates document.title and moves focus to the main area when the page changes", async () => {
    mockApi({});
    renderApp(ui);
    await waitFor(() => expect(document.title).toBe("Dashboard - Motor condition monitor"));
    fireEvent.click(await screen.findByRole("link", { name: /Assessment history/ }));
    await waitFor(() => expect(document.title).toBe("Assessment history - Motor condition monitor"));
    expect(document.activeElement?.id).toBe("main");
  });
});

// WCAG 2.x relative luminance / contrast ratio.
const lum = (hex: string) => {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
};
const ratio = (a: string, b: string) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };

describe("Colour contrast of safety-critical red (F5)", () => {
  it("white text on the red used for the Danger notice and red buttons is at least 4.5:1", () => {
    const red = [...(theme.colors?.red ?? [])];
    expect(ratio("#ffffff", red[6])).toBeGreaterThanOrEqual(4.5);
  });
});
