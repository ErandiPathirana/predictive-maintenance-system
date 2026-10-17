import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import DashboardPage from "./DashboardPage";
import EvaluationPage from "./EvaluationPage";
import HistoryPage from "./HistoryPage";
import ResultsPage from "./ResultsPage";
import UploadPage from "./UploadPage";
import { jsonResponse, mockApi, renderApp } from "../test/helpers";
import batch from "../test/fixtures/batch_response.json";
import validateBad from "../test/fixtures/validate_bad.json";
import type { HistoryItem } from "../types/api";

afterEach(() => vi.unstubAllGlobals());

const hist = (o: Partial<HistoryItem>): HistoryItem => ({
  id: 1, batch_id: null, source: "csv", record_id: "r", motor_id: "A", measured_at: "2025-01-01T00:00:00", created_at: "2026-01-01T00:00:00",
  predicted_condition: "Normal", predicted_class_id: 0, scores: { Normal: 0.9, Alert: 0.05, Danger: 0.05 }, model_version: "v1", provisional_label_provenance: true, demonstration_only: true, ...o,
});
const pageOf = (items: HistoryItem[], total = items.length) => ({ total, limit: 500, offset: 0, items });

describe("Dashboard", () => {
  it("shows an empty-data indication when nothing is stored", async () => {
    mockApi({ "/api/predictions": pageOf([]) });
    renderApp(<DashboardPage />);
    expect(await screen.findByText("No predictions stored yet")).toBeInTheDocument();
  });

  it("summarises distinct motors and the latest condition by actual timestamp", async () => {
    mockApi({
      "/api/predictions": pageOf([
        hist({ id: 3, motor_id: "A", measured_at: "2025-01-01T00:00:00", predicted_condition: "Normal" }),
        hist({ id: 2, motor_id: "A", measured_at: "2025-09-01T00:00:00", predicted_condition: "Danger" }),
        hist({ id: 1, motor_id: "B", measured_at: "2025-03-01T00:00:00", predicted_condition: "Alert" }),
      ]),
    });
    renderApp(<DashboardPage />);
    const table = await screen.findByRole("table", { name: /latest predicted condition each/i });
    const rowA = within(table).getByRole("row", { name: /^A / });
    expect(within(rowA).getByText("Danger")).toBeInTheDocument();
    expect(screen.getByText("Distinct motors").nextSibling).toHaveTextContent("2");
    expect(screen.getByTestId("not-confirmed")).toHaveTextContent(/not a confirmed machine failure/i);
  });

  it("explains an API failure and offers a retry", async () => {
    mockApi({ "/api/predictions": () => jsonResponse({ error: { code: "internal_error", message: "Database unavailable." } }, 500) });
    renderApp(<DashboardPage />);
    expect(await screen.findByText("Database unavailable.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("notes when only the newest part of the history is summarised", async () => {
    mockApi({ "/api/predictions": (url: URL) => jsonResponse({ total: 9999, limit: 500, offset: Number(url.searchParams.get("offset")), items: Number(url.searchParams.get("offset")) > 4000 ? [] : [hist({ id: Number(url.searchParams.get("offset")) + 1 })] }) });
    renderApp(<DashboardPage />);
    expect(await screen.findByText(/summarises the newest/i)).toBeInTheDocument();
  });
});

describe("History", () => {
  it("applies filters to the request and shows the model-score caveat", async () => {
    const calls = mockApi({ "/api/predictions": (url: URL) => { const items = url.searchParams.get("motor_id") === "A" ? [hist({})] : []; return jsonResponse({ total: items.length, limit: 50, offset: 0, items }); } });
    renderApp(<HistoryPage />);
    await screen.findByText("No predictions stored yet");
    await userEvent.type(screen.getByLabelText("Motor ID"), "A");
    await userEvent.click(screen.getByRole("button", { name: "Apply filters" }));
    await screen.findByRole("table", { name: /stored predictions/i });
    expect(calls.filter((c) => c.path === "/api/predictions").slice(-1)[0].url.searchParams.get("motor_id")).toBe("A");
    expect(screen.getByText("Model score (predicted class)")).toBeInTheDocument();
  });

  it("blocks an inverted date range", async () => {
    mockApi({ "/api/predictions": { total: 0, limit: 50, offset: 0, items: [] } });
    renderApp(<HistoryPage />);
    await screen.findByText("No predictions stored yet");
    await userEvent.type(screen.getByLabelText("From"), "2025-05-02");
    await userEvent.type(screen.getByLabelText("To"), "2025-05-01");
    expect(await screen.findByText(/after the "To" date/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Apply filters" })).toBeDisabled();
  });

  it("shows the backend's error message", async () => {
    mockApi({ "/api/predictions": () => jsonResponse({ error: { code: "unauthorized", message: "A valid access key is required." } }, 401) });
    renderApp(<HistoryPage />);
    expect(await screen.findByText("A valid access key is required.")).toBeInTheDocument();
    expect(screen.getByText(/Access key/)).toBeInTheDocument();
  });
});

describe("Upload", () => {
  it("shows missing required columns before anything is sent", async () => {
    const calls = mockApi({});
    renderApp(<UploadPage />);
    await waitFor(() => expect(screen.getByText(/sensor columns/)).toBeInTheDocument());
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await userEvent.upload(input, new File(["record_id,motor_id\nR1,M1\n"], "bad.csv", { type: "text/csv" }));
    expect(await screen.findByText(/required columns? (is|are) missing/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Analyse file" })).toBeDisabled();
    expect(calls.some((c) => c.path.includes("predict") || c.path.includes("validate"))).toBe(false);
  });

  it("rejects a non-CSV file with a plain message", async () => {
    mockApi({});
    renderApp(<UploadPage />);
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await userEvent.upload(input, new File(["x"], "notes.txt"), { applyAccept: false });
    expect(await screen.findByText("Please choose a .csv file.")).toBeInTheDocument();
  });

  it("lists the backend's validation problems row by row", async () => {
    mockApi({ "/api/uploads/validate": validateBad });
    renderApp(<UploadPage />);
    await waitFor(() => expect(screen.getByText(/sensor columns/)).toBeInTheDocument());
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    // contains every required column so the local check passes and the backend's report is shown
    const feats = (await import("../test/fixtures/features.json")).default.features.map((f) => f.name);
    const header = ["record_id", "motor_id", ...feats].join(",");
    const row = ["R1", "M1", ...feats.map(() => "1")].join(",");
    await userEvent.upload(input, new File([`${header}\n${row}\n`], "ok.csv", { type: "text/csv" }));
    await screen.findByText(/1 rows?, 16 columns/);
    await userEvent.click(screen.getByRole("button", { name: "Check file" }));
    expect(await screen.findByText(/File check found/)).toBeInTheDocument();
    expect(screen.getByRole("table", { name: /problems/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Analyse file" })).toBeDisabled(); // an invalid file cannot be analysed
  });
});

describe("Results", () => {
  it("explains there is nothing to show before an analysis", () => {
    mockApi({});
    renderApp(<ResultsPage />);
    expect(screen.getByText("No analysis in this session")).toBeInTheDocument();
  });

  it("renders results with the not-confirmed statement, model-score wording and version", async () => {
    mockApi({ "/api/uploads/validate": {}, "/api/predict/batch": batch });
    const { SessionProvider, useSession } = await import("../context/SessionContext");
    void SessionProvider;
    function Seed() {
      const s = useSession();
      if (!s.analysis) s.setAnalysis(batch as never);
      return <ResultsPage />;
    }
    renderApp(<Routes><Route path="/" element={<Seed />} /></Routes>);
    expect(await screen.findByText(/Prediction results/)).toBeInTheDocument();
    expect(screen.getByTestId("not-confirmed")).toBeInTheDocument();
    expect(screen.getAllByText(/not calibrated probabilities/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Model score: Normal").length).toBeGreaterThan(0);
    expect(screen.queryByText(/Probability:/)).not.toBeInTheDocument();
  });
});

describe("Model evaluation", () => {
  it("shows no numbers when no report was saved", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("nope", { status: 404 })));
    renderApp(<EvaluationPage />);
    expect(await screen.findByText(/No evaluation report has been saved/)).toBeInTheDocument();
    expect(screen.queryByText("Accuracy")).not.toBeInTheDocument();
  });

  it("refuses an unrecognised report", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({ accuracy: 0.99 })));
    renderApp(<EvaluationPage />);
    expect(await screen.findByText(/cannot be used/)).toBeInTheDocument();
    expect(screen.queryByText("Accuracy")).not.toBeInTheDocument();
  });

  const report = (origin: string, provisional = true) => ({
    schema: "pm.evaluation_report.v1", source: "t", bundle_version: "v9.9.9", created_utc: null, test_evaluated_at_utc: "2026-01-01", task: "t",
    classes: ["Normal", "Alert", "Danger"], data_origin: origin, smoke_test: false, provisional_label_provenance: provisional, label_provenance: null,
    dataset: { file_name: "d.csv", records: 100, motors: 5, time_range: null }, split: null, split_strategy: "motor-grouped", baselines: {}, bootstrap_ci_by_motor: null,
    model: {
      n: 100, accuracy: 0.9, balanced_accuracy: 0.8, macro_f1: 0.7, weighted_f1: 0.85, macro_precision: 0.7, macro_recall: 0.7, mcc: 0.6, roc_auc_ovr_macro: null, pr_auc_macro: null,
      per_class: { Normal: { precision: 0.9, recall: 0.95, f1: 0.92, support: 80 }, Alert: { precision: 0.5, recall: 0.4, f1: 0.44, support: 15 }, Danger: { precision: 0.3, recall: 0.2, f1: 0.24, support: 5 } },
      confusion_matrix: [[76, 3, 1], [8, 6, 1], [3, 1, 1]],
    },
  });

  it("shows metrics, per-class results and the confusion matrix from a valid report", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => String(input).includes("evaluation_report") ? jsonResponse(report("real")) : jsonResponse({}, 404)));
    renderApp(<EvaluationPage />);
    expect((await screen.findAllByText("0.900")).length).toBeGreaterThan(0);
    expect(screen.getByRole("table", { name: /per-class|precision, recall/i })).toBeInTheDocument();
    const cm = screen.getByRole("region", { name: "Confusion matrix" });
    expect(within(cm).getByText("76")).toBeInTheDocument();
    expect(screen.getByText(/Real data, provisional labels/)).toBeInTheDocument();
  });

  it("labels synthetic data clearly", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => String(input).includes("evaluation_report") ? jsonResponse(report("synthetic")) : jsonResponse({}, 404)));
    renderApp(<EvaluationPage />);
    expect(await screen.findByText("Synthetic demonstration")).toBeInTheDocument();
  });
});
