import { Alert, Autocomplete, Button, Group, List, SimpleGrid, Stack, Text, TextInput } from "@mantine/core";
import { useEffect, useMemo, useRef, useState } from "react";
import { ApiError, createAssessment, getMotors } from "../api/client";
import { AssessmentResult } from "../components/AssessmentResult";
import { ConfirmModal } from "../components/ConfirmModal";
import { ModelNotice, NotConfirmedStatement } from "../components/DemoNotice";
import { PageHeader } from "../components/PageHeader";
import { ErrorState, LoadingBlock } from "../components/StateViews";
import { useModel } from "../context/ModelContext";
import {
  buildRequest, emptyForm, fieldLabel, groupFeatures, hasErrors, isInFuture, MAX_DESCRIPTION, MAX_RECORDED_BY, newIdempotencyKey,
  nowLocalInput, outsideTrainingRange, validateForm, type FormValues,
} from "../lib/assessmentForm";
import type { AssessmentResponse, FeatureInfo } from "../types/api";

const fmtRange = (f: FeatureInfo) =>
  f.observed_train_min !== null && f.observed_train_max !== null ? `Seen in training data: ${f.observed_train_min.toFixed(1)} to ${f.observed_train_max.toFixed(1)}. Not a limit.` : undefined;

export default function AssessPage() {
  const { features, bundle, loading, modelError, health, reload } = useModel();
  const [values, setValues] = useState<FormValues | null>(null);
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [attempted, setAttempted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [apiError, setApiError] = useState<ApiError | Error | null>(null);
  const [result, setResult] = useState<AssessmentResponse | null>(null);
  const [confirmClear, setConfirmClear] = useState(false);
  const [motors, setMotors] = useState<string[]>([]);
  const busy = useRef(false);
  const lastPayload = useRef<string>("");
  const key = useRef<string>(newIdempotencyKey());
  const summaryRef = useRef<HTMLDivElement>(null);

  // The form is built from the model's own feature list, so names, units and order always match the loaded model.
  const form = useMemo(() => values ?? (features.length ? emptyForm(features) : null), [values, features]);
  const groups = useMemo(() => groupFeatures(features), [features]);

  useEffect(() => {
    let off = false;
    getMotors().then((m) => { if (!off) setMotors(m.items.map((i) => i.motor_id)); }).catch(() => { /* suggestions are optional */ });
    return () => { off = true; };
  }, [result]);

  if (loading) return <LoadingBlock label="Checking the model…" />;
  if (!form || !bundle) {
    return (
      <>
        <PageHeader title="New motor assessment" />
        {/* When the server cannot be reached the error box below says so; a second "no model" box would repeat it and be misleading. */}
        {!modelError && <ModelNotice />}
        {modelError && <ErrorState error={modelError} title="The model could not be checked" onRetry={reload} />}
        {!modelError && <Alert color="yellow" variant="light" title="Assessments are unavailable" role="status">{health && !health.model_ready ? "The backend is running but has no trained model loaded." : "The backend did not return the model's input list."} No prediction is made without a model.</Alert>}
      </>
    );
  }

  const errors = validateForm(form, features);
  const show = (name: string) => attempted || touched[name];
  const touch = (name: string) => setTouched((t) => ({ ...t, [name]: true }));
  const set = (patch: Partial<FormValues>) => setValues({ ...form, ...patch });
  const setReading = (name: string, v: string) => setValues({ ...form, readings: { ...form.readings, [name]: v } });
  const dirty = form.motorId || form.equipment || form.measuredAt || form.recordedBy || Object.values(form.readings).some((v) => v !== "");

  const clear = () => {
    setValues(null); setTouched({}); setAttempted(false); setApiError(null); setResult(null); setConfirmClear(false);
    key.current = newIdempotencyKey(); lastPayload.current = "";
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (busy.current) return; // a second click while the first request is running is ignored
    setAttempted(true); setApiError(null);
    if (hasErrors(errors)) {
      setTimeout(() => summaryRef.current?.focus(), 0);
      return;
    }
    const body = buildRequest(form, features);
    const payload = JSON.stringify(body);
    // The same key is reused only for an identical payload, so a retry after a timeout cannot create a second record.
    if (payload !== lastPayload.current) { key.current = newIdempotencyKey(); lastPayload.current = payload; }
    busy.current = true; setSubmitting(true);
    try {
      setResult(await createAssessment(body, key.current));
      window.scrollTo({ top: 0 });
    } catch (err) {
      setApiError(err as ApiError);
      setTimeout(() => summaryRef.current?.focus(), 0);
    } finally {
      busy.current = false; setSubmitting(false);
    }
  };

  if (result) {
    return (
      <>
        <PageHeader title="Assessment result" intro="Check the steps below, then record what was done." />
        <AssessmentResult a={result} features={features} actions={
          <>
            <Button variant="default" className="no-print" onClick={() => setResult(null)}>Edit these readings</Button>
            <Button variant="default" className="no-print" onClick={clear}>Start a new assessment</Button>
          </>
        } />
      </>
    );
  }

  const futureWarn = isInFuture(form.measuredAt);
  const problemList = [
    errors.motorId && "Motor ID", errors.measuredAt && "Measurement time",
    ...features.filter((f) => errors.readings[f.name]).map((f) => fieldLabel(f).label + ` (${groups.find((g) => g.features.includes(f))?.title ?? "input"})`),
  ].filter(Boolean) as string[];
  const details = apiError instanceof ApiError ? apiError.details as { missing_features?: string[]; unknown_features?: string[] } | undefined : undefined;

  return (
    <>
      <PageHeader title="New motor assessment" intro="Enter the readings taken from one motor. The trained model then gives its predicted condition and the recommended next steps." />
      <Stack gap="md">
        <ModelNotice compact />
        <form onSubmit={submit} noValidate aria-label="New motor assessment" className="assess-form">
          <div ref={summaryRef} tabIndex={-1} className="form-summary">
            {attempted && hasErrors(errors) && (
              <Alert color="red" variant="light" title="Some entries need fixing before the motor can be analysed" role="alert">
                <List size="sm">{problemList.map((p) => <List.Item key={p}>{p}</List.Item>)}</List>
                <Text size="sm" mt={4}>Your entries are kept. Nothing has been sent.</Text>
              </Alert>
            )}
            {apiError && (
              <ErrorState error={apiError} title={apiError instanceof ApiError && apiError.status && apiError.status < 500 ? "The server did not accept the readings" : "The assessment was not completed"} />
            )}
            {details?.missing_features?.length ? <Text size="sm" c="red.8" mt={4}>Missing: {details.missing_features.join(", ")}</Text> : null}
            {apiError && <Text size="sm" mt={4}>No result is shown and nothing is reported as saved unless the server confirms it.</Text>}
          </div>

          <fieldset className="panel form-section">
            <legend>Motor</legend>
            <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
              <Autocomplete label="Motor ID" required data={motors} value={form.motorId} onChange={(v) => set({ motorId: v })} onBlur={() => touch("motor")}
                description="Pick a motor you have assessed before, or type its ID." placeholder="For example MOT01" maxLength={64}
                error={show("motor") ? errors.motorId : undefined} autoComplete="off" />
              <TextInput label="Measurement date and time" required type="datetime-local" value={form.measuredAt} onChange={(e) => set({ measuredAt: e.currentTarget.value })} onBlur={() => touch("time")}
                description="When the readings were taken, in local time." error={show("time") ? errors.measuredAt : undefined}
                rightSectionWidth={110} rightSection={<Button size="compact-xs" variant="subtle" onClick={() => set({ measuredAt: nowLocalInput() })}>Use now</Button>} />
              <TextInput label="Equipment description (optional)" value={form.equipment} onChange={(e) => set({ equipment: e.currentTarget.value })} maxLength={MAX_DESCRIPTION + 20}
                description="For example: Pump 3 drive motor." error={errors.equipment} />
              <TextInput label="Recorded by (optional)" value={form.recordedBy} onChange={(e) => set({ recordedBy: e.currentTarget.value })} maxLength={MAX_RECORDED_BY + 20}
                description="Your name or initials. This is not verified: there is no login." error={errors.recordedBy} />
            </SimpleGrid>
            {futureWarn && <Text size="sm" c="orange.9" mt="xs" role="status">This time is in the future. Check the date and clock.</Text>}
          </fieldset>

          {groups.map((g) => (
            <fieldset className="panel form-section" key={g.id}>
              <legend>{g.title}</legend>
              <SimpleGrid cols={{ base: 1, xs: 2, md: 3 }} spacing="md">
                {g.features.map((f) => {
                  const { label, unit } = fieldLabel(f);
                  return (
                    <TextInput key={f.name} label={unit ? `${label} (${unit})` : label} required inputMode="decimal" autoComplete="off"
                      value={form.readings[f.name] ?? ""} onChange={(e) => setReading(f.name, e.currentTarget.value)} onBlur={() => touch(f.name)}
                      description={fmtRange(f)} error={show(f.name) ? errors.readings[f.name] : undefined}
                      data-testid={`field-${f.name}`} name={f.name} />
                  );
                })}
              </SimpleGrid>
              {g.features.map((f) => {
                const soft = outsideTrainingRange(f, form.readings[f.name] ?? "");
                return soft ? <Text key={f.name} size="sm" c="orange.9" mt="xs" role="status">{fieldLabel(f).label} ({g.title}): {soft}</Text> : null;
              })}
            </fieldset>
          ))}

          <NotConfirmedStatement />
          <Group mt="sm" className="form-actions">
            <Button type="submit" size="md" loading={submitting} disabled={submitting}>Analyse motor</Button>
            <Button variant="default" size="md" disabled={submitting || !dirty} onClick={() => setConfirmClear(true)}>Clear form</Button>
            {submitting && <Text size="sm" role="status">Analysing with the trained model…</Text>}
          </Group>
        </form>
      </Stack>
      <ConfirmModal opened={confirmClear} title="Clear the form?" message="All the values you entered will be removed." confirmLabel="Clear form" onConfirm={clear} onCancel={() => setConfirmClear(false)} />
    </>
  );
}
