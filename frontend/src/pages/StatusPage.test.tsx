import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StatusPage } from "./StatusPage";

const health = { status: "ok", app_name: "API", app_version: "0.2.0", environment: "test", model_ready: false, database: "ok" };

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
    expect(screen.getAllByText("Checking")).toHaveLength(3);
    await screen.findByText("Not loaded"); // let the load finish before the test ends
  });

  it("tells the user when the model is not loaded, and why", async () => {
    stubApi({ model_ready: false, reason: "The prediction model is not available on the server." });
    render(<StatusPage />);
    expect(await screen.findByText("Not loaded")).toBeInTheDocument();
    expect(screen.getByText(/prediction model is not available/)).toBeInTheDocument();
    expect(screen.getByText("Connected")).toBeInTheDocument();
  });

  it("shows model details and the demonstration banner when the model is ready", async () => {
    stubApi({
      model_ready: true,
      bundle: {
        model_name: "test-model", bundle_version: "v9", classes: [{ id: 0, name: "Normal" }, { id: 1, name: "Alert" }],
        feature_count: 14, features: [], label_provenance_documented: false, provisional_label_provenance: true,
        demonstration_only: true, deployable_for_decisions: false, scores_are_calibrated_probabilities: false,
        future_failure_prediction_supported: false, smoke_test_bundle: false, notes: ["Predicted condition class only."],
      },
    });
    render(<StatusPage />);
    expect(await screen.findByText("Ready")).toBeInTheDocument();
    expect(screen.getByText("test-model")).toBeInTheDocument();
    expect(screen.getByText("v9")).toBeInTheDocument();
    expect(screen.getByText("Normal, Alert")).toBeInTheDocument();
    expect(screen.getByText(/Not documented/)).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent("Demonstration only");
  });

  it("shows a database fault when history storage is unavailable", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => ({
      ok: true,
      json: async () => (String(url).endsWith("/health") ? { ...health, database: "unavailable" } : { model_ready: false }),
    })) as unknown as typeof fetch);
    render(<StatusPage />);
    expect(await screen.findByText("Unavailable")).toBeInTheDocument();
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
