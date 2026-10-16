import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StatusPage } from "./StatusPage";

const health = { status: "ok", app_name: "API", app_version: "0.1.0", environment: "test", model_ready: false };

function stubApi(modelInfo: object) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => ({
      ok: true,
      json: async () => (String(url).endsWith("/health") ? health : modelInfo),
    })) as unknown as typeof fetch,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("StatusPage", () => {
  it("shows a checking state first", async () => {
    stubApi({ model_ready: false });
    render(<StatusPage />);
    expect(screen.getAllByText("Checking")).toHaveLength(2);
    await screen.findByText("Not loaded"); // let the load finish before the test ends
  });

  it("tells the user when the model is not loaded, and why", async () => {
    stubApi({ model_ready: false, reason: "Missing model file(s): model.joblib." });
    render(<StatusPage />);
    expect(await screen.findByText("Not loaded")).toBeInTheDocument();
    expect(screen.getByText(/Missing model file/)).toBeInTheDocument();
  });

  it("shows model details when the model is ready", async () => {
    stubApi({
      model_ready: true,
      feature_count: 3,
      metadata: { model_name: "test-model", model_version: "v9", positive_class: 1 },
    });
    render(<StatusPage />);
    expect(await screen.findByText("Ready")).toBeInTheDocument();
    expect(screen.getByText("test-model")).toBeInTheDocument();
    expect(screen.getByText("v9")).toBeInTheDocument();
  });

  it("shows an error with a retry button when the server is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("down"); }) as unknown as typeof fetch);
    render(<StatusPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach the prediction server");
    expect(screen.getByText("Not reachable")).toBeInTheDocument();

    stubApi({ model_ready: false });
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Running")).toBeInTheDocument();
  });
});
