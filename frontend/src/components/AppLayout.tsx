import { AppShell, Burger, Button, Group, NavLink, Text } from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { useEffect, useRef, useState } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";
import { useModel } from "../context/ModelContext";
import { AccessKeyModal } from "./AccessKeyModal";

export const NAV_ITEMS = [
  { to: "/", label: "Dashboard", hint: "Overview of all motors" },
  { to: "/assess", label: "New assessment", hint: "Enter readings and get next steps" },
  { to: "/monitoring", label: "Motor monitoring", hint: "Sensor trends for one motor" },
  { to: "/upload", label: "Upload a CSV file", hint: "Check and analyse many records" },
  { to: "/results", label: "Prediction results", hint: "Results of the latest analysis" },
  { to: "/history", label: "Assessment history", hint: "Saved results, steps and export" },
] as const;

const APP_NAME = "Motor condition monitor";
/** Title for the browser tab and screen readers. Detail pages are not in the menu, so they are matched by prefix. */
export function titleFor(pathname: string): string {
  if (pathname.startsWith("/assessment/")) return `Assessment details - ${APP_NAME}`;
  const item = NAV_ITEMS.find((n) => (n.to === "/" ? pathname === "/" : pathname.startsWith(n.to)));
  return item ? `${item.label} - ${APP_NAME}` : `Page not found - ${APP_NAME}`;
}

function BackendLamp() {
  const { loading, health, healthError, bundle } = useModel();
  let text: string, color: string, shape: "circle" | "triangle" | "diamond";
  if (loading) { text = "Checking backend…"; color = "var(--text-muted)"; shape = "circle"; }
  else if (!health) { text = healthError?.code === "timeout" ? "Backend not answering" : "Backend unreachable"; color = "var(--status-danger)"; shape = "diamond"; }
  else if (!health.model_ready || !bundle) { text = "Backend up, no model"; color = "#ffd27a"; shape = "triangle"; }
  else { text = `Model ${bundle.bundle_version} ready`; color = "#7be0a0"; shape = "circle"; }
  return (
    <Text size="sm" c="white" role="status" aria-live="polite" data-testid="backend-lamp" style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
      <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
        {shape === "circle" && <circle cx="6" cy="6" r="5" fill={color} />}
        {shape === "triangle" && <path d="M6 1 11.5 11 .5 11Z" fill={color} />}
        {shape === "diamond" && <path d="M6 .5 11.5 6 6 11.5.5 6Z" fill={color} />}
      </svg>
      <span className="lamp-text">{text}</span>
    </Text>
  );
}

export function AppLayout() {
  const [opened, { toggle, close }] = useDisclosure(false);
  const [keyOpen, setKeyOpen] = useState(false);
  const { pathname } = useLocation();
  const { reload } = useModel();
  // A single-page app does not reload, so without this a screen-reader or keyboard user is never told the page changed.
  const first = useRef(true);
  useEffect(() => {
    document.title = titleFor(pathname);
    if (first.current) { first.current = false; return; }
    document.getElementById("main")?.focus({ preventScroll: true });
    window.scrollTo?.({ top: 0 });
  }, [pathname]);
  return (
    <>
      {/* The app uses HashRouter, so a plain href="#main" would be read as the route "/main" and show "Page not found". Move focus by script instead. */}
      <a href="#main" className="skip-link" onClick={(e) => { e.preventDefault(); const m = document.getElementById("main"); m?.focus(); m?.scrollIntoView?.(); }}>Skip to main content</a>
      <AppShell header={{ height: 56 }} navbar={{ width: 250, breakpoint: "md", collapsed: { mobile: !opened } }} padding="md">
        <AppShell.Header style={{ background: "var(--nav-bg)", borderBottom: "1px solid #0d2129" }}>
          <Group h="100%" px="md" justify="space-between" wrap="nowrap">
            <Group wrap="nowrap">
              <Burger opened={opened} onClick={toggle} hiddenFrom="md" size="sm" color="white" aria-label={opened ? "Close navigation" : "Open navigation"} />
              <Link to="/" className="brand" onClick={close}>Motor condition monitor<small>Predictive maintenance research prototype</small></Link>
            </Group>
            <Group gap="md" wrap="nowrap">
                            <BackendLamp />
              <Button size="compact-sm" variant="white" color="dark" onClick={() => setKeyOpen(true)} aria-label="Access key">Key<span className="key-long">&nbsp;(access)</span></Button>
            </Group>
          </Group>
        </AppShell.Header>
        <AppShell.Navbar p="sm" style={{ background: "var(--nav-bg)", borderRight: "none" }} aria-label="Main">
          <nav aria-label="Main navigation">
            {NAV_ITEMS.map((n) => (
              <NavLink
                key={n.to} component={Link} to={n.to} className="nav-link" label={n.label} description={n.hint}
                active={n.to === "/" ? pathname === "/" : pathname.startsWith(n.to)}
                aria-current={(n.to === "/" ? pathname === "/" : pathname.startsWith(n.to)) ? "page" : undefined}
                onClick={close}
                styles={{ description: { color: "#a9c4cb" } }}
              />
            ))}
          </nav>
        </AppShell.Navbar>
        <AppShell.Main id="main" tabIndex={-1}>
          <div style={{ maxWidth: 1200, margin: "0 auto" }}><Outlet /></div>
        </AppShell.Main>
      </AppShell>
      <AccessKeyModal opened={keyOpen} onClose={() => setKeyOpen(false)} onSaved={reload} />
    </>
  );
}
