import { ApiError, getHealth } from "./client";

const mockFetch = (impl: () => Promise<Partial<Response>>) =>
  vi.stubGlobal("fetch", vi.fn(impl) as unknown as typeof fetch);

afterEach(() => vi.unstubAllGlobals());

describe("api client", () => {
  it("returns parsed JSON on success", async () => {
    mockFetch(async () => ({ ok: true, json: async () => ({ status: "ok", model_ready: false }) }));
    expect(await getHealth()).toMatchObject({ status: "ok" });
  });

  it("turns the backend's structured error into an ApiError", async () => {
    mockFetch(async () => ({
      ok: false,
      status: 503,
      json: async () => ({ error: { code: "model_not_ready", message: "No model yet." } }),
    }));
    await expect(getHealth()).rejects.toMatchObject({ code: "model_not_ready", message: "No model yet.", status: 503 });
  });

  it("handles non-JSON error bodies", async () => {
    mockFetch(async () => ({
      ok: false,
      status: 502,
      json: async () => {
        throw new Error("not json");
      },
    }));
    await expect(getHealth()).rejects.toBeInstanceOf(ApiError);
  });

  it("explains network failures in plain English", async () => {
    mockFetch(async () => {
      throw new TypeError("Failed to fetch");
    });
    await expect(getHealth()).rejects.toMatchObject({ code: "network_error" });
  });
});
