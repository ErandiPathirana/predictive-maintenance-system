import { Alert, Button, FileInput, Group, List, Loader, Stack, Text, Title } from "@mantine/core";
import { useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, downloadReport, downloadTemplate, predictBatch, saveFile, validateCsv } from "../api/client";
import { ConditionBadge } from "../components/ConditionBadge";
import { ConfirmModal } from "../components/ConfirmModal";
import { DataTable } from "../components/DataTable";
import { ModelNotice, NotConfirmedStatement } from "../components/DemoNotice";
import { PageHeader } from "../components/PageHeader";
import { ErrorState } from "../components/StateViews";
import { useModel } from "../context/ModelContext";
import { useSession } from "../context/SessionContext";
import { missingColumns, parseCsvFile, quickFileCheck, CLIENT_MAX_ROWS } from "../lib/csvFile";
import { CONDITION_ORDER } from "../lib/condition";
import { formatInt } from "../lib/format";

type Phase = "idle" | "reading" | "checking" | "analysing";

export default function UploadPage() {
  const { bundle, features } = useModel();
  const s = useSession();
  const [phase, setPhase] = useState<Phase>("idle");
  const [localProblem, setLocalProblem] = useState<string | null>(null);
  const [apiError, setApiError] = useState<ApiError | Error | null>(null);
  const [confirmClear, setConfirmClear] = useState(false);
  const featureNames = features.map((f) => f.name);
  const busy = phase !== "idle";
  const missing = s.dataset && featureNames.length ? missingColumns(s.dataset.columns, featureNames) : [];

  const onFile = async (file: File | null) => {
    setApiError(null); setLocalProblem(null);
    if (!file) { s.clear(); return; }
    const problem = quickFileCheck(file);
    if (problem) { setLocalProblem(problem); s.clear(); return; }
    setPhase("reading");
    try {
      const parsed = await parseCsvFile(file);
      if (parsed.columns.length === 0 || parsed.rows.length === 0) { setLocalProblem("The file has no data rows. Check that the first row contains column names."); s.clear(); }
      else if (parsed.rows.length > CLIENT_MAX_ROWS) { setLocalProblem(`The file has ${formatInt(parsed.rows.length)} rows. The default limit is ${formatInt(CLIENT_MAX_ROWS)} rows.`); s.clear(); }
      else s.setDataset({ fileName: file.name, columns: parsed.columns, rows: parsed.rows, loadedAt: new Date() }, file);
    } catch {
      setLocalProblem("The file could not be read as CSV."); s.clear();
    } finally { setPhase("idle"); }
  };

  const run = async (kind: "check" | "analyse") => {
    if (!s.file) return;
    setApiError(null); setPhase(kind === "check" ? "checking" : "analysing");
    try {
      if (kind === "check") s.setValidation(await validateCsv(s.file));
      else s.setAnalysis(await predictBatch(s.file));
    } catch (e) { setApiError(e as ApiError); } finally { setPhase("idle"); }
  };

  const download = async (fn: () => Promise<Parameters<typeof saveFile>[0]>) => {
    setApiError(null);
    try { saveFile(await fn()); } catch (e) { setApiError(e as ApiError); }
  };

  const previewCols = s.dataset ? s.dataset.columns.slice(0, 8) : [];
  const v = s.validation;
  const canAnalyse = !!s.file && !busy && !!bundle && (v === null || v.valid) && missing.length === 0;

  return (
    <>
      <PageHeader title="Upload and analyse" intro="Check a CSV file of sensor readings, then ask the model for the predicted condition of each record." />
      <ModelNotice compact />
      <Stack gap="lg" mt="md">
        <section className="panel" aria-labelledby="step1">
          <Title order={2} size="h4" id="step1">1. Get the template</Title>
          <Text size="sm" mb="xs">The file needs these columns, spelled exactly like this. <code>measured_at</code> is optional but needed for time-based charts and for "latest" on the dashboard.</Text>
          <Text size="sm" c="dimmed" mb="xs" component="div">
            {featureNames.length ? (<>Required: <code>record_id</code>, <code>motor_id</code>, then {featureNames.length} sensor columns:{" "}
              <span style={{ wordBreak: "break-word" }}>{featureNames.join(", ")}.</span></>) : "The column list appears once the backend answers."}
          </Text>
          <Text size="sm" c="dimmed" mb="xs">
            Use <code>YYYY-MM-DD HH:MM:SS</code> for times, one format on every row. Extra columns are ignored. Up to {formatInt(CLIENT_MAX_ROWS)} rows and 2 MB by default.
          </Text>
          <Button variant="default" onClick={() => download(downloadTemplate)} disabled={!bundle}>Download CSV template</Button>
        </section>

        <section className="panel" aria-labelledby="step2">
          <Title order={2} size="h4" id="step2">2. Choose your file</Title>
          <FileInput label="CSV file" placeholder="Select a .csv file" accept=".csv,text/csv" value={s.file} onChange={onFile} clearable disabled={busy} maw={460}
            description="The file is read in your browser first. It is sent to the server only when you press Check or Analyse." />
          {phase === "reading" && <Group mt="xs" role="status"><Loader size="xs" /><Text size="sm">Reading file…</Text></Group>}
          {localProblem && <Alert color="red" variant="light" mt="sm" role="alert" title="This file cannot be used">{localProblem}</Alert>}
          {s.dataset && (
            <Stack gap="xs" mt="md">
              <Text size="sm"><strong>{s.dataset.fileName}</strong>: {formatInt(s.dataset.rows.length)} rows, {s.dataset.columns.length} columns.</Text>
              {missing.length > 0 && (
                <Alert color="red" variant="light" role="alert" title={`${missing.length} required column${missing.length === 1 ? " is" : "s are"} missing`}>
                  <Text size="sm" style={{ wordBreak: "break-word" }}>{missing.join(", ")}</Text>
                  <Text size="sm">Column names must match exactly. Download the template and copy your values into it.</Text>
                </Alert>
              )}
              <DataTable
                caption="Preview of the first 5 rows (first 8 columns)"
                rows={s.dataset.rows.slice(0, 5)} rowKey={(_, i) => i}
                columns={previewCols.map((c) => ({ key: c, header: c, render: (r: Record<string, string>) => r[c] }))}
              />
            </Stack>
          )}
        </section>

        <section className="panel" aria-labelledby="step3">
          <Title order={2} size="h4" id="step3">3. Check, then analyse</Title>
          <Text size="sm" mb="sm">Checking changes nothing on the server. Analysing stores one prediction per record in the history.</Text>
          <Group>
            <Button variant="default" onClick={() => run("check")} disabled={!s.file || busy || !bundle} loading={phase === "checking"}>Check file</Button>
            <Button onClick={() => run("analyse")} disabled={!canAnalyse} loading={phase === "analysing"}>Analyse file</Button>
            {s.dataset && <Button variant="subtle" color="red" onClick={() => setConfirmClear(true)} disabled={busy}>Remove file from this page</Button>}
          </Group>
          {phase === "analysing" && <Text size="sm" mt="xs" role="status">Analysing {s.dataset ? formatInt(s.dataset.rows.length) : ""} records. Large files can take a little while.</Text>}
          {!bundle && <Text size="sm" c="dimmed" mt="xs">Checking and analysing are unavailable until the backend reports a loaded model.</Text>}
          {apiError && <div style={{ marginTop: 12 }}><ErrorState error={apiError} title="The server could not process the request" /></div>}

          {v && (
            <div style={{ marginTop: 16 }} aria-live="polite">
              {v.valid ? (
                <Alert color="green" variant="light" title="File check passed">{formatInt(v.record_count)} records are in the expected format.
                  {v.ignored_columns.length > 0 && ` Ignored columns: ${v.ignored_columns.join(", ")}.`}</Alert>
              ) : (
                <>
                  <Alert color="red" variant="light" title={`File check found ${formatInt(v.issues_total)} problem${v.issues_total === 1 ? "" : "s"}`} role="alert">
                    Nothing was stored. Fix the items below in your file and choose it again.
                  </Alert>
                  <div style={{ marginTop: 8 }}>
                    <DataTable
                      caption={v.issues.length < v.issues_total ? `First ${v.issues.length} of ${v.issues_total} problems` : "Problems found"}
                      rows={v.issues} rowKey={(_, i) => i}
                      columns={[
                        { key: "row", header: "File row", numeric: true, render: (r) => (r.row ?? "All") },
                        { key: "col", header: "Column", render: (r) => r.column ?? "Whole file" },
                        { key: "p", header: "Problem", render: (r) => r.problem },
                      ]}
                    />
                  </div>
                </>
              )}
            </div>
          )}
        </section>

        {s.analysis && (
          <section className="panel" aria-labelledby="done" aria-live="polite">
            <Title order={2} size="h4" id="done">Analysis complete</Title>
            <Text size="sm" mb="xs">{formatInt(s.analysis.record_count)} records from <strong>{s.analysis.filename}</strong> were analysed with model {s.analysis.model_version}.</Text>
            <Group gap="sm" mb="xs">
              {CONDITION_ORDER.map((c) => (<Group key={c} gap={6}><ConditionBadge condition={c} /><Text size="sm">{formatInt(s.analysis!.class_counts[c] ?? 0)}</Text></Group>))}
            </Group>
            <NotConfirmedStatement />
            <List size="sm" mt="xs" spacing={2}>
              <List.Item>Predicted condition counts are model estimates, not confirmed failures.</List.Item>
            </List>
            <Group mt="md">
              <Button component={Link} to="/results">View results</Button>
              <Button component={Link} to="/monitoring" variant="default">See sensor trends</Button>
              <Button variant="default" onClick={() => download(() => downloadReport({ batch_id: s.analysis!.batch_id }))}>Download results (CSV)</Button>
            </Group>
          </section>
        )}
      </Stack>
      <ConfirmModal opened={confirmClear} title="Remove this file?" confirmLabel="Remove file"
        message="This clears the file, the check result and the analysis summary from this page. Predictions already stored on the server stay in the history."
        onCancel={() => setConfirmClear(false)} onConfirm={() => { s.clear(); setConfirmClear(false); setLocalProblem(null); setApiError(null); }} />
    </>
  );
}
