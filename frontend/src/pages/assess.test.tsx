import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import AssessPage from "./AssessPage";
import AssessmentDetailPage from "./AssessmentDetailPage";
import { jsonResponse, mockApi, renderApp } from "../test/helpers";
import features from "../test/fixtures/features.json";
import okAssessment from "../test/fixtures/assessment.json";
import danger from "../test/fixtures/assessment_danger.json";
import invalid from "../test/fixtures/assessment_invalid.json";
import motors from "../test/fixtures/motors.json";

afterEach(() => vi.unstubAllGlobals());

const F = features.features;
const motorBox = () => screen.getByRole("combobox", { name: /Motor ID/ }) as HTMLInputElement;
const fieldBox = (name: string) => screen.getByTestId(`field-${name}`) as HTMLInputElement;

async function fill(user: ReturnType<typeof userEvent.setup>, opts: { skip?: string; motor?: string } = {}) {
  await user.type(motorBox(), opts.motor ?? "MOT01");
  await user.type(screen.getByLabelText(/Measurement date and time/), "2025-04-01T07:20");
  for (const [i, f] of F.entries()) if (f.name !== opts.skip) await user.type(fieldBox(f.name), String(10 + i));
}

describe("New assessment form", () => {
  it("shows every model input, grouped by bearing position, in the model's order", async () => {
    mockApi({ "/api/motors": motors });
    renderApp(<AssessPage />);
    expect(await screen.findByRole("heading", { name: "New motor assessment" })).toBeInTheDocument();
    for (const t of ["Drive end, horizontal", "Drive end, vertical", "Non-drive end, horizontal", "Non-drive end, vertical", "Operating conditions"]) {
      expect(screen.getByText(t, { selector: "legend" })).toBeInTheDocument();
    }
    const names = screen.getAllByRole("textbox").map((e) => (e as HTMLInputElement).name).filter((n) => F.some((f) => f.name === n));
    expect(names).toEqual(F.map((f) => f.name));
  });

  it("explains missing and invalid fields, keeps entries, and sends nothing", async () => {
    const calls = mockApi({ "/api/motors": motors });
    const user = userEvent.setup();
    renderApp(<AssessPage />);
    await screen.findByRole("heading", { name: "New motor assessment" });
    await user.type(motorBox(), "MOT01");
    await user.type(fieldBox(F[0].name), "abc");
    await user.click(screen.getByRole("button", { name: "Analyse motor" }));
    expect(await screen.findByText(/Some entries need fixing/)).toBeInTheDocument();
    expect(screen.getByText(/Nothing has been sent/)).toBeInTheDocument();
    expect(screen.getAllByText(/Missing readings are never replaced with zero/).length).toBeGreaterThan(0);
    expect(fieldBox(F[0].name).value).toBe("abc");
    expect(motorBox().value).toBe("MOT01");
    expect(calls.some((c) => c.path === "/api/assessments")).toBe(false);
  });

  it("submits valid readings with an Idempotency-Key and shows the saved result with its steps", async () => {
    const calls = mockApi({ "/api/motors": motors, "/api/assessments": okAssessment });
    const user = userEvent.setup();
    renderApp(<AssessPage />);
    await screen.findByRole("heading", { name: "New motor assessment" });
    await fill(user);
    await user.click(screen.getByRole("button", { name: "Analyse motor" }));
    expect(await screen.findByTestId("assessment-result")).toBeInTheDocument();
    const post = calls.find((c) => c.path === "/api/assessments")!;
    expect(post.init?.method).toBe("POST");
    expect((post.init?.headers as Record<string, string>)["Idempotency-Key"]).toMatch(/^form-/);
    const sent = JSON.parse(String(post.init?.body));
    expect(sent.motor_id).toBe("MOT01");
    expect(sent.readings[F[0].name]).toBe(10);
    expect(Object.keys(sent.readings)).toHaveLength(14);
    expect(screen.getByText(/Saved as assessment/)).toBeInTheDocument();
    expect(screen.getAllByTestId("rec-item").length).toBeGreaterThan(0);
    expect(screen.getByTestId("not-confirmed")).toHaveTextContent(/not a confirmed machine failure/i);
    expect(screen.getByText(/not calibrated probabilities/i)).toBeInTheDocument();
  });

  it("shows the Danger notice with safety wording for a Danger result", async () => {
    mockApi({ "/api/motors": motors, "/api/assessments": danger });
    const user = userEvent.setup();
    renderApp(<AssessPage />);
    await screen.findByRole("heading", { name: "New motor assessment" });
    await fill(user);
    await user.click(screen.getByRole("button", { name: "Analyse motor" }));
    const notice = await screen.findByTestId("danger-notice");
    expect(notice).toHaveTextContent(/not a confirmed fault and not a shutdown order/i);
    expect(notice).toHaveTextContent(/lockout\/tagout/i);
    expect(screen.getByTestId("result-banner")).toHaveAttribute("data-condition", "Danger");
    expect(screen.getByText(/Before the motor returns to service/)).toBeInTheDocument();
  });

  it("ignores a second click while the first request is running (one request only)", async () => {
    let resolve!: (r: Response) => void;
    const pending = new Promise<Response>((r) => { resolve = r; });
    const calls = mockApi({ "/api/motors": motors, "/api/assessments": () => pending as unknown as Response });
    const user = userEvent.setup();
    renderApp(<AssessPage />);
    await screen.findByRole("heading", { name: "New motor assessment" });
    await fill(user);
    const btn = screen.getByRole("button", { name: "Analyse motor" });
    await user.click(btn);
    await user.click(btn);
    expect(calls.filter((c) => c.path === "/api/assessments")).toHaveLength(1);
    expect(screen.getByText(/Analysing with the trained model/)).toBeInTheDocument();
    expect(screen.queryByText(/Saved as assessment/)).not.toBeInTheDocument();
    resolve(jsonResponse(okAssessment, 201));
    expect(await screen.findByText(/Saved as assessment/)).toBeInTheDocument();
  });

  it("does not claim a save when the database fails, and keeps the readings", async () => {
    mockApi({ "/api/motors": motors, "/api/assessments": () => jsonResponse({ error: { code: "database_unavailable", message: "The result could not be saved, so nothing was recorded." } }, 503) });
    const user = userEvent.setup();
    renderApp(<AssessPage />);
    await screen.findByRole("heading", { name: "New motor assessment" });
    await fill(user);
    await user.click(screen.getByRole("button", { name: "Analyse motor" }));
    expect(await screen.findByText(/nothing was recorded/)).toBeInTheDocument();
    expect(screen.queryByText(/Saved as assessment/)).not.toBeInTheDocument();
    expect(screen.queryByTestId("assessment-result")).not.toBeInTheDocument();
    expect(fieldBox(F[3].name).value).toBe("13");
  });

  it("reports a network failure without showing a result", async () => {
    mockApi({ "/api/motors": motors, "/api/assessments": () => { throw new TypeError("Failed to fetch"); } });
    const user = userEvent.setup();
    renderApp(<AssessPage />);
    await screen.findByRole("heading", { name: "New motor assessment" });
    await fill(user);
    await user.click(screen.getByRole("button", { name: "Analyse motor" }));
    expect(await screen.findByText(/Cannot reach the prediction server/)).toBeInTheDocument();
    expect(screen.queryByTestId("assessment-result")).not.toBeInTheDocument();
  });

  it("shows the server's explanation when it rejects the readings", async () => {
    mockApi({ "/api/motors": motors, "/api/assessments": () => jsonResponse(invalid, 422) });
    const user = userEvent.setup();
    renderApp(<AssessPage />);
    await screen.findByRole("heading", { name: "New motor assessment" });
    await fill(user);
    await user.click(screen.getByRole("button", { name: "Analyse motor" }));
    expect(await screen.findByText(/No prediction was made/)).toBeInTheDocument();
    expect(screen.getByText(/Missing: de_h_ge/)).toBeInTheDocument();
  });

  it("asks before clearing, and keeps the values if you cancel", async () => {
    mockApi({ "/api/motors": motors });
    const user = userEvent.setup();
    renderApp(<AssessPage />);
    await screen.findByRole("heading", { name: "New motor assessment" });
    expect(screen.getByRole("button", { name: "Clear form" })).toBeDisabled();
    await user.type(fieldBox(F[0].name), "12");
    await user.click(screen.getByRole("button", { name: "Clear form" }));
    expect(await screen.findByText("All the values you entered will be removed.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Keep it" }));
    await waitFor(() => expect(screen.queryByText("All the values you entered will be removed.")).not.toBeInTheDocument());
    expect(fieldBox(F[0].name).value).toBe("12");
    await user.click(screen.getByRole("button", { name: "Clear form" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Clear form" }));
    await waitFor(() => expect(fieldBox(F[0].name).value).toBe(""));
  });

  it("warns, without blocking, when a value is outside the training range", async () => {
    mockApi({ "/api/motors": motors });
    const user = userEvent.setup();
    renderApp(<AssessPage />);
    await screen.findByRole("heading", { name: "New motor assessment" });
    await user.type(fieldBox(F[0].name), "9999");
    expect(await screen.findByText(/not an alarm limit/i)).toBeInTheDocument();
  });

  it("refuses to run without a model", async () => {
    mockApi({ "/api/model-info": { model_ready: false, reason: "No bundle", bundle: null }, "/api/health": { status: "degraded", app_name: "x", app_version: "1", environment: "t", model_ready: false, database: "ok" } });
    renderApp(<AssessPage />);
    expect(await screen.findByText(/Assessments are unavailable/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Analyse motor" })).not.toBeInTheDocument();
  });
});

describe("Saved assessment page", () => {
  it("reopens a stored record with its recommendations and no 'saved' banner", async () => {
    mockApi({ "/api/assessments/5": { ...okAssessment, assessment_id: 5, readings: null } });
    renderApp(<Routes><Route path="/assessment/:id" element={<AssessmentDetailPage />} /></Routes>, "/assessment/5");
    expect(await screen.findByTestId("assessment-result")).toBeInTheDocument();
    expect(screen.queryByText(/Saved as assessment/)).not.toBeInTheDocument();
    expect(screen.getByText(/does not store raw sensor readings/i)).toBeInTheDocument();
  });

  it("explains a missing record", async () => {
    mockApi({ "/api/assessments/99": () => jsonResponse({ error: { code: "not_found", message: "No assessment with that number." } }, 404) });
    renderApp(<Routes><Route path="/assessment/:id" element={<AssessmentDetailPage />} /></Routes>, "/assessment/99");
    expect(await screen.findByText("No assessment with that number.")).toBeInTheDocument();
  });
});
