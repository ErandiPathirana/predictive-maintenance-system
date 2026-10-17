import { MantineProvider } from "@mantine/core";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { ModelProvider } from "../context/ModelContext";
import { SessionProvider } from "../context/SessionContext";
import { theme } from "../theme";
import health from "./fixtures/health.json";
import modelInfo from "./fixtures/model_info.json";
import features from "./fixtures/features.json";

export type Routes = Record<string, unknown | ((url: URL, init?: RequestInit) => Response | Promise<Response>)>;

export const jsonResponse = (body: unknown, status = 200, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json", ...headers } });

/** Replaces fetch. Keys are URL paths. Anything not listed fails the test loudly, so no hidden calls slip through. */
export function mockApi(routes: Routes) {
  const calls: { path: string; url: URL; init?: RequestInit }[] = [];
  const all: Routes = { "/api/health": health, "/api/model-info": modelInfo, "/api/features": features, ...routes };
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "http://test");
    calls.push({ path: url.pathname, url, init });
    if (!(url.pathname in all)) throw new Error(`Unmocked request: ${url.pathname}`);
    const r = all[url.pathname];
    return typeof r === "function" ? (r as (u: URL, i?: RequestInit) => Response)(url, init) : jsonResponse(r);
  }));
  return calls;
}

export function renderApp(ui: ReactElement, route = "/") {
  return render(
    <MantineProvider theme={theme} forceColorScheme="light">
      <ModelProvider>
        <SessionProvider>
          <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
        </SessionProvider>
      </ModelProvider>
    </MantineProvider>,
  );
}
