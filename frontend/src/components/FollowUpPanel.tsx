import { Alert, Badge, Button, Group, List, Modal, Select, Stack, Text, Textarea, TextInput, Title } from "@mantine/core";
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { addMaintenanceUpdate, ApiError, emailReport, getEmailStatus, getMaintenance, openMaintenanceCase } from "../api/client";
import { formatTimestamp } from "../lib/format";
import { assessmentRef, isFollowUpCondition, isValidEmail, STATUS_LABEL, STATUS_ORDER } from "../lib/maintenance";
import type { AssessmentResponse, EmailStatus, MaintenanceCase, MaintenanceDetail, MaintenanceStatus, MaintenanceUpdate, MaintenanceUpdateRequest } from "../types/api";
import { BeforeAfter } from "./BeforeAfter";
import { ErrorState, LoadingBlock } from "./StateViews";

const clean = <T extends object>(o: T) => Object.fromEntries(Object.entries(o).filter(([, v]) => v !== "" && v !== undefined && v !== null)) as T;

/* ---------------- e-mail ---------------- */
function EmailDialog({ a, opened, onClose, onSent }: { a: AssessmentResponse; opened: boolean; onClose: () => void; onSent: () => void }) {
  const [status, setStatus] = useState<EmailStatus | null>(null);
  const [to, setTo] = useState("");
  const [note, setNote] = useState("");
  const [touched, setTouched] = useState(false);
  const [sending, setSending] = useState(false);
  const [done, setDone] = useState<{ ok: true; text: string } | { ok: false; text: string } | null>(null);
  const busy = useRef(false);

  useEffect(() => {
    if (!opened) return;
    setDone(null); setTouched(false);
    getEmailStatus().then(setStatus).catch(() => setStatus(null));
  }, [opened]);

  const recipient = to.trim();
  const invalid = !isValidEmail(recipient);
  const send = async () => {
    setTouched(true);
    if (invalid || busy.current || done?.ok) return;       // a second click while sending (or after success) does nothing
    busy.current = true; setSending(true); setDone(null);
    try {
      // Readings are sent only when the server did not keep them. The server re-checks that they reproduce this saved result.
      const r = await emailReport(a.assessment_id, { recipient, ...(note.trim() ? { note: note.trim() } : {}), ...(a.readings && !a.readings_stored ? { readings: a.readings } : {}) });
      setDone({ ok: true, text: `The mail server accepted the report for ${r.recipient} at ${formatTimestamp(r.sent_at)} (UTC). ${r.message}` });
      onSent();
    } catch (e) {
      setDone({ ok: false, text: e instanceof ApiError ? e.message : "The report could not be sent." });
    } finally { busy.current = false; setSending(false); }
  };

  return (
    <Modal opened={opened} onClose={onClose} title="Email assessment report" size="lg">
      <Stack gap="sm">
        {status && !status.configured && <Alert color="yellow" variant="light" role="alert" title="E-mail is not set up on this server">No report can be sent until the administrator sets the mail settings. See the deployment guide.</Alert>}
        <TextInput label="Recipient e-mail address (responsible Plant Engineer)" type="email" value={to} onChange={(e) => setTo(e.currentTarget.value)} onBlur={() => setTouched(true)}
          error={touched && invalid ? "Enter one valid e-mail address, for example name@company.com." : undefined} disabled={sending || !!done?.ok} autoComplete="off"
          description={status?.recipients_restricted ? "Only approved company domains are accepted on this server." : undefined} />
        <Textarea label="Note to add (optional)" value={note} onChange={(e) => setNote(e.currentTarget.value)} maxLength={500} rows={2} disabled={sending || !!done?.ok} />
        <section aria-label="Report summary">
          <Title order={3} size="h5">Review before sending</Title>
          <List size="sm" spacing={2}>
            <List.Item>To: {recipient || "(enter an address)"}</List.Item>
            <List.Item>Motor {a.motor_id ?? "not recorded"}, reference {assessmentRef(a.assessment_id)}</List.Item>
            <List.Item>Predicted condition: <strong>{a.predicted_condition}</strong>, readings taken {formatTimestamp(a.measured_at)}</List.Item>
            <List.Item>{a.readings ? "Sensor readings will be included." : "Sensor readings will not be included: the server does not store them and they are no longer on screen."}</List.Item>
            <List.Item>{status?.link_in_report ? "A link to this assessment will be included." : "No link is included (no public address is configured)."}</List.Item>
          </List>
          <Text size="xs" c="dimmed" mt={4}>The report states that the result is decision support and needs interpretation by a qualified engineer.</Text>
        </section>
        <div role="status" aria-live="polite">
          {sending && <Text size="sm">Sending…</Text>}
          {done && <Alert color={done.ok ? "green" : "red"} variant="light" title={done.ok ? "Accepted by the mail server" : "Report not sent"}>{done.text}</Alert>}
        </div>
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>{done?.ok ? "Close" : "Cancel"}</Button>
          {!done?.ok && <Button onClick={send} loading={sending} disabled={sending || (status !== null && !status.configured)}>Send report</Button>}
        </Group>
      </Stack>
    </Modal>
  );
}

/* ---------------- follow-up ---------------- */
function Steps({ current }: { current: MaintenanceStatus }) {
  const at = STATUS_ORDER.indexOf(current);
  return (
    <ol className="followup-steps" aria-label="Maintenance status">
      {STATUS_ORDER.map((s, i) => (
        <li key={s} aria-current={i === at ? "step" : undefined} style={{ fontWeight: i === at ? 700 : 400 }}>
          <span aria-hidden="true">{i < at ? "✔ " : i === at ? "▶ " : "○ "}</span>{STATUS_LABEL[s]}{i === at ? " (current)" : i < at ? " (done)" : ""}
        </li>
      ))}
    </ol>
  );
}

function LogEntry({ u }: { u: MaintenanceUpdate }) {
  const rows: [string, string | null][] = [
    ["Engineer", u.responsible_engineer], ["Started", u.started_on], ["Completed", u.completed_on], ["Fault or issue found", u.fault_found],
    ["Actions performed", u.actions_performed], ["Parts and notes", u.parts_notes], ["Comment", u.comment],
    ["Verification outcome", u.verification_outcome === "verified" ? "Verified" : u.verification_outcome === "not_verified" ? "Not verified: more work needed" : null],
    ["Reassessment date", u.reassessment_date], ["Entered by (not verified)", u.updated_by],
  ];
  return (
    <li className="log-entry">
      <Text size="sm" fw={600}>{formatTimestamp(u.created_at)} UTC: {u.kind === "opened" ? "Follow-up opened" : u.kind === "reassessment" ? `Reassessment #${u.reassessment_assessment_id} linked` : "Update"}: {STATUS_LABEL[u.to_status]}</Text>
      <List size="sm" listStyleType="none" spacing={0}>{rows.filter(([, v]) => v).map(([k, v]) => <List.Item key={k}>{k}: {v}</List.Item>)}</List>
    </li>
  );
}

function UpdateForm({ c, onSaved }: { c: MaintenanceCase; onSaved: (c: MaintenanceCase) => void }) {
  const awaitingVerification = c.status === "repair_completed_verification_required";
  const next = c.allowed_next_statuses;
  const [target, setTarget] = useState<string>(c.status);
  const [f, setF] = useState({ updated_by: "", responsible_engineer: "", started_on: "", completed_on: "", fault_found: "", actions_performed: "", parts_notes: "", comment: "", reassessment_date: "" });
  const [outcome, setOutcome] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const busy = useRef(false);
  const set = (k: keyof typeof f) => (e: { currentTarget: { value: string } }) => setF({ ...f, [k]: e.currentTarget.value });

  const to = (awaitingVerification ? (outcome === "verified" ? "verified_closed" : outcome === "not_verified" ? "maintenance_in_progress" : c.status) : target) as MaintenanceStatus;
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (busy.current) return;
    busy.current = true; setSaving(true); setErr(null);
    try {
      const body = clean({ to_status: to, ...f, ...(awaitingVerification && outcome ? { verification_outcome: outcome } : {}) }) as MaintenanceUpdateRequest;
      onSaved(await addMaintenanceUpdate(c.id, body));
      setF({ updated_by: f.updated_by, responsible_engineer: "", started_on: "", completed_on: "", fault_found: "", actions_performed: "", parts_notes: "", comment: "", reassessment_date: "" });
      setOutcome(null); setTarget("");
    } catch (x) { setErr(x instanceof ApiError ? x.message : "The update was not saved."); }
    finally { busy.current = false; setSaving(false); }
  };
  const options = [{ value: c.status, label: `Add a note (stay at ${STATUS_LABEL[c.status]})` }, ...next.map((s) => ({ value: s, label: `Move to: ${STATUS_LABEL[s]}` }))];
  const showStart = to === "maintenance_in_progress";
  const showDone = to === "repair_completed_verification_required";

  return (
    <form onSubmit={submit} aria-label="Record a maintenance update">
      <Stack gap="xs">
        {awaitingVerification ? (
          <Select label="Verification outcome" description="Recorded by the person who verified the motor under the site's procedures." placeholder="Choose, or leave empty to add a note only" clearable
            data={[{ value: "verified", label: "Verified: close the case" }, { value: "not_verified", label: "Not verified: more work needed (back to Maintenance In Progress)" }]} value={outcome} onChange={setOutcome} />
        ) : (
          <Select label="What are you recording?" data={options} value={target} onChange={(v) => v && setTarget(v)} allowDeselect={false} />
        )}
        <TextInput label={outcome === "verified" ? "Verified by (name or initials)" : "Your name or initials"} description="Not verified: there is no login." value={f.updated_by} onChange={set("updated_by")} maxLength={64} required={outcome === "verified"} />
        <TextInput label="Responsible engineer" value={f.responsible_engineer} onChange={set("responsible_engineer")} maxLength={64} />
        {showStart && <TextInput label="Maintenance start date" type="date" value={f.started_on} onChange={set("started_on")} />}
        {(showStart || showDone) && <Textarea label="Fault or issue found" value={f.fault_found} onChange={set("fault_found")} maxLength={1000} rows={2} />}
        {showDone && (
          <>
            <TextInput label="Completion date" type="date" value={f.completed_on} onChange={set("completed_on")} />
            <Textarea label="Repair or maintenance actions performed" required value={f.actions_performed} onChange={set("actions_performed")} maxLength={1000} rows={2} />
            <TextInput label="Spare parts or other notes (optional)" value={f.parts_notes} onChange={set("parts_notes")} maxLength={500} />
          </>
        )}
        {awaitingVerification && <TextInput label="Date of reassessment (optional)" type="date" value={f.reassessment_date} onChange={set("reassessment_date")} />}
        <Textarea label={outcome === "not_verified" ? "Comment (required: say why)" : "Engineer comment"} required={outcome === "not_verified"} value={f.comment} onChange={set("comment")} maxLength={1000} rows={2} />
        {err && <Alert color="red" variant="light" role="alert">{err}</Alert>}
        <Group><Button type="submit" loading={saving} disabled={saving}>Save update</Button></Group>
      </Stack>
    </form>
  );
}

export function FollowUpPanel({ a, readableName }: { a: AssessmentResponse; readableName?: (n: string) => string }) {
  const nav = useNavigate();
  const [d, setD] = useState<MaintenanceDetail | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [emailOpen, setEmailOpen] = useState(false);
  const [opening, setOpening] = useState(false);
  const eligible = isFollowUpCondition(a.predicted_condition);
  const load = useCallback(() => getMaintenance(a.assessment_id).then((x) => { setD(x); setError(null); }).catch((e) => setError(e)), [a.assessment_id]);
  useEffect(() => { void load(); }, [load]);

  const c = d?.case ?? null;
  const lastSent = d?.emails.find((e) => e.status === "sent");
  const lastFailed = d?.emails[0]?.status === "failed" ? d.emails[0] : null;

  return (
    <>
      {d?.follows_assessment_id && (
        <Alert color="blue" variant="light" role="note" data-testid="follows-note">
          This is a reassessment linked to the follow-up on assessment {assessmentRef(d.follows_assessment_id)}. Open that record to compare and to record the verification outcome.{" "}
          <Button component="a" href={`#/assessment/${d.follows_assessment_id}`} variant="subtle" size="compact-sm">Open original assessment</Button>
        </Alert>
      )}
      {eligible && (
        <section className="panel no-print" aria-labelledby="fu-h" data-testid="followup-panel">
          <Title order={2} size="h3" id="fu-h">Notify and follow up</Title>
          <Text size="sm" c="dimmed">Nothing is sent automatically. The system never shuts down or controls equipment.</Text>
          <Group mt="sm">
            <Button onClick={() => setEmailOpen(true)}>Email Assessment Report</Button>
          </Group>
          <div role="status" aria-live="polite">
            {lastSent && <Text size="sm" mt="xs" data-testid="report-sent">Report accepted by the mail server for {lastSent.recipient} on {formatTimestamp(lastSent.created_at)} (UTC).</Text>}
            {lastFailed && <Text size="sm" mt="xs" c="red.8">The last attempt to send the report failed. Nothing was sent.</Text>}
          </div>

          <Title order={3} size="h4" mt="md">Maintenance follow-up</Title>
          {!d && !error && <LoadingBlock label="Loading follow-up…" />}
          {error && <ErrorState error={error} title="Could not load the follow-up" onRetry={() => void load()} />}
          {d && !c && (
            d.eligible
              ? <>
                  <Text size="sm" mb="xs">No follow-up has been started for this assessment. Start one to track inspection, repair and verification. The assessment above stays unchanged.</Text>
                  <Button variant="default" loading={opening} disabled={opening} onClick={async () => {
                    setOpening(true);
                    try { setD(await openMaintenanceCase(a.assessment_id)); } catch (e) { setError(e as Error); } finally { setOpening(false); }
                  }}>Start maintenance follow-up</Button>
                </>
              : <Text size="sm">{d.reason ?? "A follow-up cannot be started for this assessment."}</Text>
          )}
          {c && (
            <Stack gap="sm" mt="xs">
              <Group gap="xs"><Badge className="pill" radius="sm" tt="none" data-testid="case-status">{c.status_label}</Badge><Text size="sm">Case {c.reference} · opened on assessment {c.assessment_reference}</Text></Group>
              <Steps current={c.status} />
              {c.status === "repair_completed_verification_required" && (
                <Alert color="blue" variant="light" title="Verification required" role="note">
                  Reassess the motor with fresh readings, then record the verification outcome. A Normal result does not close the case.
                  <Group mt="xs"><Button data-testid="reassess" onClick={() => nav(`/assess?motor_id=${encodeURIComponent(c.motor_id)}&case=${c.id}`)}>Reassess Motor</Button></Group>
                </Alert>
              )}
              {c.reassessments.map((r) => (
                <div key={r.assessment_id}>
                  <Title order={4} size="h5">Reassessment #{r.assessment_id} ({formatTimestamp(r.created_at)} UTC)</Title>
                  <BeforeAfter readableName={readableName}
                    before={{ label: `Original ${c.assessment_reference}`, condition: a.predicted_condition, readings: a.readings, scores: a.scores }}
                    after={{ label: `Reassessment ${assessmentRef(r.assessment_id)}`, condition: r.predicted_condition, readings: r.readings, scores: r.scores }} />
                  <Button component="a" href={`#/assessment/${r.assessment_id}`} variant="subtle" size="compact-sm">Open reassessment</Button>
                </div>
              ))}
              {c.status === "verified_closed"
                ? <Alert color="green" variant="light" role="status">This case is verified and closed. It cannot be changed.</Alert>
                : <UpdateForm key={`${c.id}-${c.status}-${c.updates.length}`} c={c} onSaved={() => void load()} />}
              <section aria-label="Maintenance history">
                <Title order={4} size="h5">Maintenance notes (oldest first)</Title>
                <ol className="log-list">{c.updates.map((u) => <LogEntry key={u.id} u={u} />)}</ol>
              </section>
            </Stack>
          )}
        </section>
      )}
      {eligible && <EmailDialog a={a} opened={emailOpen} onClose={() => setEmailOpen(false)} onSent={() => void load()} />}
    </>
  );
}
