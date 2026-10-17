import { ApiError, downloadReport, getBaseUrl, getEvaluationReport, getHealth, getPredictions, hasAccessKey, predictBatch, setAccessKey } from "./client";

const stub = (impl: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>) => vi.stubGlobal("fetch", vi.fn(impl));
const ok = (body: unknown, headers: Record<string, string> = {}) => new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json", ...headers } });

afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); setAccessKey(null); });

describe("api client", () => {
  it("returns parsed JSON on success", async () => {
    stub(async () => ok({ status: "ok" }));
    expect(await getHealth()).toMatchObject({ status: "ok" });
  });

  it("uses the base URL from the environment variable, without a trailing slash", () => {
    vi.stubEnv("VITE_API_BASE_URL", "https://api.example.org/");
    expect(getBaseUrl()).toBe("https://api.example.org");
    vi.unstubAllEnvs();
  });

  it("turns the backend's structured error into an ApiError", async () => {
    stub(async () => new Response(JSON.stringify({ error: { code: "invalid_csv", message: "Bad file.", details: { x: 1 } } }), { status: 422 }));
    await expect(getHealth()).rejects.toMatchObject({ code: "invalid_csv", message: "Bad file.", status: 422, details: { x: 1 } });
  });

  it("handles non-JSON error bodies", async () => {
    stub(async () => new Response("<html>Bad gateway</html>", { status: 502 }));
    const err = await getHealth().catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(502);
  });

  it("explains network failures in plain English", async () => {
    stub(async () => { throw new TypeError("Failed to fetch"); });
    await expect(getHealth()).rejects.toMatchObject({ code: "network_error" });
  });

  it("reports a timeout when the server does not answer", async () => {
    vi.useFakeTimers();
    stub((_i, init) => new Promise((_res, rej) => { init?.signal?.addEventListener("abort", () => rej(Object.assign(new Error("aborted"), { name: "AbortError" }))); }));
    const p = getHealth().catch((e) => e);
    await vi.advanceTimersByTimeAsync(21_000);
    expect(await p).toMatchObject({ code: "timeout" });
  });

  it("sends the access key only as a header, only when set", async () => {
    const f = vi.fn(async () => ok({}));
    vi.stubGlobal("fetch", f);
    await getHealth();
    expect((f.mock.calls[0] as unknown as [string, RequestInit])[1].headers).toBeUndefined();
    setAccessKey("  secret  ");
    expect(hasAccessKey()).toBe(true);
    await getHealth();
    const [url, init] = f.mock.calls[1] as unknown as [string, RequestInit];
    expect(init.headers).toEqual({ "X-API-Key": "secret" });
    expect(url).not.toContain("secret");
  });

  it("builds history queries and skips empty filters", async () => {
    const f = vi.fn(async () => ok({ total: 0, limit: 50, offset: 0, items: [] }));
    vi.stubGlobal("fetch", f);
    await getPredictions({ motor_id: "M 1", predicted_condition: "" }, 50, 100);
    const url = new URL((f.mock.calls[0] as unknown as [string])[0]);
    expect(url.pathname).toBe("/api/predictions");
    expect(url.searchParams.get("motor_id")).toBe("M 1");
    expect(url.searchParams.get("limit")).toBe("50");
    expect(url.searchParams.get("offset")).toBe("100");
    expect(url.searchParams.has("predicted_condition")).toBe(false);
  });

  it("uploads a CSV as multipart form data", async () => {
    const f = vi.fn(async () => ok({ batch_id: "b" }));
    vi.stubGlobal("fetch", f);
    await predictBatch(new File(["a,b\n1,2\n"], "x.csv", { type: "text/csv" }));
    const [url, init] = f.mock.calls[0] as unknown as [string, RequestInit];
    expect(new URL(url).pathname).toBe("/api/predict/batch");
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
    expect((init.body as FormData).get("file")).toBeInstanceOf(File);
  });

  it("reads export headers so truncation is never silent", async () => {
    stub(async () => new Response("a,b\r\n", { status: 200, headers: { "content-type": "text/csv", "content-disposition": 'attachment; filename="p.csv"', "x-total-matching": "90000", "x-rows-exported": "50000", "x-export-truncated": "true" } }));
    const file = await downloadReport({});
    expect(file).toMatchObject({ filename: "p.csv", truncated: true, totalMatching: 90000, rowsExported: 50000 });
  });

  it("treats a missing evaluation report (404 or HTML fallback) as 'none'", async () => {
    stub(async () => new Response("Not found", { status: 404 }));
    expect(await getEvaluationReport()).toBeNull();
    stub(async () => new Response("<html></html>", { status: 200, headers: { "content-type": "text/html" } }));
    expect(await getEvaluationReport()).toBeNull();
  });
});
