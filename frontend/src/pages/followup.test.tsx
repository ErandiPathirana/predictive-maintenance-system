import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import AssessPage from "./AssessPage";
import AssessmentDetailPage from "./AssessmentDetailPage";
import HistoryPage from "./HistoryPage";
import { jsonResponse, mockApi, renderApp } from "../test/helpers";
import danger from "../test/fixtures/assessment_danger.json";
import ok from "../test/fixtures/assessment.json";
import features from "../test/fixtures/features.json";
import motors from "../test/fixtures/motors.json";
import type { MaintenanceCase, MaintenanceDetail } from "../types/api";

afterEach(() => vi.unstubAllGlobals());

const ID = danger.assessment_id;
const alertA = { ...danger, predicted_condition: "Alert", recommendations: { ...danger.recommendations, urgent: false } };
const noCase: MaintenanceDetail = { assessment_id: ID, predicted_condition: "Danger", eligible: true, reason: null, case: null, emails: [], follows_assessment_id: null, follows_case_id: null };
const mkCase = (status: MaintenanceCase["status"], extra: Partial<MaintenanceCase> = {}): MaintenanceCase => ({
  id: 3, reference: "MC-00003", assessment_id: ID, assessment_reference: "PM-000009", motor_id: "MOT02", status, status_label: status, created_at: "2026-01-01T00:00:00", updated_at: "2026-01-01T00:00:00",
  allowed_next_statuses: status === "pending_inspection" ? ["maintenance_in_progress"] : [], updates: [], reassessments: [], ...extra,
});
const withCase = (c: MaintenanceCase, emails: MaintenanceDetail["emails"] = []): MaintenanceDetail => ({ ...noCase, eligible: false, case: c, emails });
const email = { configured: true, recipients_restricted: false, link_in_report: false, max_per_hour: 20 };

function open(routes: Parameters<typeof mockApi>[0], rec = danger as unknown) {
  const calls = mockApi({ [`/api/assessments/${ID}`]: rec, ...routes });
  renderApp(<Routes><Route path="/assessment/:id" element={<AssessmentDetailPage />} /></Routes>, `/assessment/${ID}`);
  return calls;
}

describe("Result display", () => {
  it("Danger shows the required wording with the model's own label, plus the reference and the e-mail button", async () => {
    open({ [`/api/assessments/${ID}/maintenance`]: noCase });
    const n = await screen.findByTestId("danger-notice");
    expect(n).toHaveTextContent("Attention: This motor has been classified as Danger by the assessment system. Contact the responsible Plant Engineer immediately for inspection and follow the site's approved safety procedures.");
    expect(n).toHaveTextContent(/not a shutdown order/);
    expect(screen.getByTestId("assessment-ref")).toHaveTextContent(`PM-${String(ID).padStart(6, "0")}`);
    expect(await screen.findByRole("button", { name: "Email Assessment Report" })).toBeInTheDocument();
  });

  it("Alert shows a prominent, text-labelled warning (not colour alone) and the e-mail button", async () => {
    open({ [`/api/assessments/${ID}/maintenance`]: noCase }, alertA);
    const n = await screen.findByTestId("alert-notice");
    expect(n).toHaveTextContent(/classified as Alert/);
    expect(n).toHaveTextContent(/Prompt inspection by the responsible Plant Engineer/);
    expect(screen.queryByTestId("danger-notice")).toBeNull();
    expect(await screen.findByRole("button", { name: "Email Assessment Report" })).toBeInTheDocument();
  });

  it("Normal shows neither warning nor e-mail/follow-up controls", async () => {
    mockApi({ [`/api/assessments/${ok.assessment_id}`]: ok, [`/api/assessments/${ok.assessment_id}/maintenance`]: { ...noCase, assessment_id: ok.assessment_id, predicted_condition: "Normal", eligible: false } });
    renderApp(<Routes><Route path="/assessment/:id" element={<AssessmentDetailPage />} /></Routes>, `/assessment/${ok.assessment_id}`);
    await screen.findByTestId("assessment-result");
    expect(screen.queryByTestId("danger-notice")).toBeNull();
    expect(screen.queryByTestId("alert-notice")).toBeNull();
    expect(screen.queryByRole("button", { name: "Email Assessment Report" })).toBeNull();
    expect(screen.queryByTestId("followup-panel")).toBeNull();
  });
});

describe("Email dialog", () => {
  async function openDialog(post: (u: URL, i?: RequestInit) => Response | Promise<Response>, detail = noCase) {
    const calls = open({ [`/api/assessments/${ID}/maintenance`]: detail, "/api/email-status": email, [`/api/assessments/${ID}/email-report`]: post });
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Email Assessment Report" }));
    const dlg = await screen.findByRole("dialog");
    return { calls, user, dlg };
  }

  it("rejects an invalid address without calling the server", async () => {
    const { calls, user, dlg } = await openDialog(() => jsonResponse({}));
    await user.type(within(dlg).getByLabelText(/Recipient e-mail/), "not-an-email");
    await user.click(within(dlg).getByRole("button", { name: "Send report" }));
    expect(await within(dlg).findByText(/valid e-mail address/)).toBeInTheDocument();
    expect(calls.some((c) => c.path.endsWith("/email-report"))).toBe(false);
  });

  it("shows a review summary, sends once even on a double click, and words success as 'accepted' (not 'delivered')", async () => {
    let resolve!: (r: Response) => void;
    const pending = new Promise<Response>((r) => { resolve = r; });
    const { calls, user, dlg } = await openDialog(() => pending as unknown as Response);
    expect(within(dlg).getByText(/Review before sending/)).toBeInTheDocument();
    await user.type(within(dlg).getByLabelText(/Recipient e-mail/), "eng@plant.test");
    const send = within(dlg).getByRole("button", { name: "Send report" });
    await user.click(send); await user.click(send);
    expect(await within(dlg).findByText("Sending…")).toBeInTheDocument();
    resolve(jsonResponse({ sent: true, assessment_id: ID, reference: "PM", recipient: "eng@plant.test", sent_at: "2026-01-01T10:00:00", readings_included: true, message: "The mail server accepted the report. This does not guarantee it reached the inbox." }));
    expect(await within(dlg).findByText("Accepted by the mail server")).toBeInTheDocument();
    expect(within(dlg).getByText(/does not guarantee/)).toBeInTheDocument();
    const posts = calls.filter((c) => c.path.endsWith("/email-report"));
    expect(posts).toHaveLength(1);
    const sent = JSON.parse(String(posts[0].init?.body));
    expect(sent.recipient).toBe("eng@plant.test");
    expect(sent.readings).toBeTruthy();                      // the transient readings travel with the request; they are not stored
  });

  it("reports a failure as a failure and never as sent", async () => {
    const { user, dlg } = await openDialog(() => jsonResponse({ error: { code: "email_failed", message: "The report could not be sent because the mail server could not be reached. Nothing was sent." } }, 502));
    await user.type(within(dlg).getByLabelText(/Recipient e-mail/), "eng@plant.test");
    await user.click(within(dlg).getByRole("button", { name: "Send report" }));
    expect(await within(dlg).findByText("Report not sent")).toBeInTheDocument();
    expect(within(dlg).getByText(/Nothing was sent/)).toBeInTheDocument();
    expect(within(dlg).queryByText(/Accepted by the mail server/)).toBeNull();
    expect(within(dlg).getByRole("button", { name: "Send report" })).toBeEnabled();      // can retry
  });

  it("disables sending and explains when e-mail is not configured", async () => {
    open({ [`/api/assessments/${ID}/maintenance`]: noCase, "/api/email-status": { ...email, configured: false } });
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Email Assessment Report" }));
    const dlg = await screen.findByRole("dialog");
    expect(await within(dlg).findByText(/E-mail is not set up on this server/)).toBeInTheDocument();
    expect(within(dlg).getByRole("button", { name: "Send report" })).toBeDisabled();
  });

  it("shows when a report was accepted, from the stored record", async () => {
    open({ [`/api/assessments/${ID}/maintenance`]: { ...noCase, emails: [{ id: 1, recipient: "eng@plant.test", status: "sent", error_summary: null, created_at: "2026-01-01T10:00:00" }] } });
    expect(await screen.findByTestId("report-sent")).toHaveTextContent(/eng@plant.test.*2026-01-01 10:00/);
  });
});

describe("Maintenance follow-up", () => {
  it("starts a follow-up (Pending Inspection) without changing the assessment", async () => {
    const started = withCase(mkCase("pending_inspection"));
    let n = 0;
    open({ [`/api/assessments/${ID}/maintenance`]: () => jsonResponse(noCase), [`/api/assessments/${ID}/maintenance-case`]: () => { n++; return jsonResponse(started, 201); } });
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Start maintenance follow-up" }));
    expect(await screen.findByTestId("case-status")).toBeInTheDocument();
    expect(n).toBe(1);
    expect(screen.getByTestId("danger-notice")).toBeInTheDocument();       // original result still shown unchanged
  });

  it("sends a status update with only the filled fields", async () => {
    const calls = open({ [`/api/assessments/${ID}/maintenance`]: withCase(mkCase("pending_inspection")), "/api/maintenance-cases/3/updates": () => jsonResponse(mkCase("maintenance_in_progress")) });
    const user = userEvent.setup();
    await screen.findByRole("form", { name: "Record a maintenance update" });
    await user.click(screen.getByRole("textbox", { name: /Your name or initials/ }));
    await user.type(screen.getByRole("textbox", { name: /Your name or initials/ }), "JP");
    await user.click(screen.getByRole("combobox", { name: "What are you recording?" }));
    await user.click(await screen.findByRole("option", { name: /Move to: Maintenance In Progress/, hidden: true }));
    await user.click(screen.getByRole("button", { name: "Save update" }));
    await waitFor(() => expect(calls.some((c) => c.path === "/api/maintenance-cases/3/updates")).toBe(true));
    const body = JSON.parse(String(calls.find((c) => c.path === "/api/maintenance-cases/3/updates")?.init?.body));
    expect(body).toEqual({ to_status: "maintenance_in_progress", updated_by: "JP" });
  });

  it("offers Reassess Motor only after repair completion, and a closed case is read-only", async () => {
    open({ [`/api/assessments/${ID}/maintenance`]: withCase(mkCase("repair_completed_verification_required", { allowed_next_statuses: ["verified_closed", "maintenance_in_progress"] })) });
    expect(await screen.findByRole("button", { name: "Reassess Motor" })).toBeInTheDocument();
    expect(screen.getByText(/A Normal result does not close the case/)).toBeInTheDocument();
  });

  it("a closed case is read-only", async () => {
    open({ [`/api/assessments/${ID}/maintenance`]: withCase(mkCase("verified_closed")) });
    await waitFor(() => expect(screen.getAllByText(/verified and closed/).length).toBeGreaterThan(0));
    expect(screen.queryByRole("form", { name: "Record a maintenance update" })).toBeNull();
  });

  it("compares conditions always, and readings only when both are available", async () => {
    const re = { assessment_id: 12, created_at: "2026-02-01T00:00:00", measured_at: null, predicted_condition: "Normal", scores: { Normal: 0.9, Alert: 0.05, Danger: 0.05 }, readings: null };
    open({ [`/api/assessments/${ID}/maintenance`]: withCase(mkCase("repair_completed_verification_required", { reassessments: [re] })) });
    const ba = await screen.findByTestId("before-after");
    expect(within(ba).getByRole("table", { name: /condition before and after/i })).toBeInTheDocument();
    expect(within(ba).getByText(/Readings are not compared/)).toBeInTheDocument();
    expect(within(ba).getByText(/not verification/)).toBeInTheDocument();
  });
});

describe("Reassess flow on the New Assessment page", () => {
  it("prefills the motor ID, saves a separate assessment and links it to the case", async () => {
    const f0 = features.features[0].name;
    const calls = mockApi({
      "/api/motors": motors, "/api/assessments": ok, [`/api/assessments/${ID}`]: danger,
      "/api/maintenance-cases/3/reassessments": () => jsonResponse(mkCase("repair_completed_verification_required")),
    });
    const user = userEvent.setup();
    renderApp(<AssessPage />, "/assess?motor_id=MOT02&case=3");
    await screen.findByRole("heading", { name: "New motor assessment" });
    expect((screen.getByRole("combobox", { name: /Motor ID/ }) as HTMLInputElement).value).toBe("MOT02");
    await user.type(screen.getByLabelText(/Measurement date and time/), "2025-04-01T07:20");
    for (const [i, f] of features.features.entries()) await user.type(screen.getByTestId(`field-${f.name}`), String(10 + i));
    expect(f0).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Analyse motor" }));
    expect(await screen.findByTestId("linked-note")).toHaveTextContent(/Linked to follow-up MC-00003/);
    const link = calls.find((c) => c.path === "/api/maintenance-cases/3/reassessments");
    expect(JSON.parse(String(link?.init?.body))).toEqual({ assessment_id: ok.assessment_id });
    expect(screen.getByText(/A Normal prediction after a repair is not verification|not verification/)).toBeInTheDocument();
  });
});

describe("Assessment history", () => {
  it("filters by maintenance status and shows status and report columns", async () => {
    const item = { id: 5, batch_id: null, source: "single", record_id: null, motor_id: "MOT02", measured_at: "2025-01-01T00:00:00", created_at: "2026-01-01T00:00:00", predicted_condition: "Danger", predicted_class_id: 2,
      scores: { Normal: 0.05, Alert: 0.05, Danger: 0.9 }, model_version: "v1", provisional_label_provenance: true, demonstration_only: true,
      maintenance_status: "pending_inspection", maintenance_case_id: 1, report_sent_at: "2026-01-01T10:00:00" };
    const re = { ...item, id: 6, predicted_condition: "Normal", maintenance_status: null, report_sent_at: null, follows_assessment_id: 5 };
    const calls = mockApi({ "/api/predictions": { total: 2, limit: 50, offset: 0, items: [re, item] } });
    const user = userEvent.setup();
    renderApp(<HistoryPage />);
    const table = await screen.findByRole("table", { name: /Stored predictions/ });
    expect(within(table).getByText("Pending Inspection")).toBeInTheDocument();
    expect(within(table).getByText(/Accepted 2026-01-01 10:00/)).toBeInTheDocument();
    expect(within(table).getByText("Reassessment of #5")).toBeInTheDocument();
    await user.click(screen.getByRole("combobox", { name: "Maintenance status" }));
    await user.click(await screen.findByRole("option", { name: /Open: awaiting/, hidden: true }));
    await user.click(screen.getByRole("button", { name: "Apply filters" }));
    await waitFor(() => expect(calls.some((c) => c.url.searchParams.get("maintenance_status") === "open")).toBe(true));
  });
});
