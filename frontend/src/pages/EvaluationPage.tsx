import { Alert, Code, SimpleGrid, Text, Title } from "@mantine/core";
import { useEffect, useState } from "react";
import { ApiError, getEvaluationReport } from "../api/client";
import { DataTable } from "../components/DataTable";
import { PageHeader } from "../components/PageHeader";
import { StatCard } from "../components/StatCard";
import { EmptyState, ErrorState, LoadingBlock } from "../components/StateViews";
import { useModel } from "../context/ModelContext";
import { checkReport, type EvaluationReport, type ModelMetrics } from "../lib/evaluation";
import { formatInt, formatMetric } from "../lib/format";

type Load = { s: "loading" } | { s: "error"; e: ApiError } | { s: "none" } | { s: "invalid"; reason: string } | { s: "ok"; report: EvaluationReport };

export function OriginNotice({ report }: { report: EvaluationReport }) {
  if (report.smoke_test) return <Alert color="red" variant="light" title="Smoke-test numbers">This report comes from a quick debugging run. The numbers mean nothing.</Alert>;
  if (report.data_origin === "synthetic")
    return <Alert color="yellow" variant="light" title="Synthetic demonstration">These numbers were measured on generated data. They show that the software works. They are not evidence of how well the model performs on a real plant.</Alert>;
  if (report.data_origin === "unknown")
    return <Alert color="yellow" variant="light" title="Data origin not recorded">The report does not say whether the data was real or synthetic. Treat the numbers as unverified until it is stated.</Alert>;
  if (report.provisional_label_provenance)
    return <Alert color="blue" variant="light" title="Real data, provisional labels">The numbers are measured on real data, but the origin of the Alert and Danger labels is not yet verified. They describe agreement with those labels, not with confirmed failures.</Alert>;
  return <Alert color="blue" variant="light" title="Real data, documented labels">Measured on held-out test motors from real data with documented label provenance.</Alert>;
}

function ConfusionMatrix({ classes, matrix }: { classes: string[]; matrix: number[][] }) {
  return (
    <div className="table-wrap" role="region" aria-label="Confusion matrix" tabIndex={0} style={{ padding: 12 }}>
      <table className="cm">
        <caption style={{ textAlign: "left", paddingBottom: 6, color: "var(--text-secondary)", fontSize: 13 }}>
          Rows: actual label in the data. Columns: condition the model predicted. Each cell shows the count and the share of its row.
        </caption>
        <thead>
          <tr><td style={{ border: "none" }} /><th scope="col" colSpan={classes.length}>Predicted</th></tr>
          <tr><th scope="col">Actual</th>{classes.map((c) => <th key={c} scope="col">{c}</th>)}</tr>
        </thead>
        <tbody>
          {matrix.map((row, i) => {
            const total = row.reduce((a, b) => a + b, 0);
            return (
              <tr key={classes[i]}>
                <th scope="row">{classes[i]}</th>
                {row.map((v, j) => {
                  const share = total ? v / total : 0;
                  return (
                    <td key={j} style={{ background: `rgba(15,92,115,${(0.08 + share * 0.5).toFixed(2)})`, borderWidth: i === j ? 2 : 1, borderColor: i === j ? "var(--accent)" : undefined }}>
                      <strong>{formatInt(v)}</strong><span>{total ? `${(share * 100).toFixed(1)}%` : "n/a"}</span>
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function Metrics({ m, classes }: { m: ModelMetrics; classes: string[] }) {
  return (
    <>
      <SimpleGrid cols={{ base: 2, sm: 3, lg: 6 }} spacing="sm" mb="md">
        <StatCard label="Test records" value={formatInt(m.n)} />
        <StatCard label="Accuracy" value={formatMetric(m.accuracy)} />
        <StatCard label="Balanced accuracy" value={formatMetric(m.balanced_accuracy)} />
        <StatCard label="Macro F1" value={formatMetric(m.macro_f1)} />
        <StatCard label="Weighted F1" value={formatMetric(m.weighted_f1)} />
        <StatCard label="Matthews corr." value={formatMetric(m.mcc)} />
      </SimpleGrid>
      <Title order={3} size="h5" mb="xs">Per-class results</Title>
      <DataTable
        caption="Precision, recall and F1 for each class on the test set"
        rows={classes} rowKey={(c) => c}
        columns={[
          { key: "c", header: "Class (actual label)", render: (c) => c },
          { key: "p", header: "Precision", numeric: true, render: (c) => formatMetric(m.per_class[c]?.precision) },
          { key: "r", header: "Recall", numeric: true, render: (c) => formatMetric(m.per_class[c]?.recall) },
          { key: "f", header: "F1", numeric: true, render: (c) => formatMetric(m.per_class[c]?.f1) },
          { key: "s", header: "Test records", numeric: true, render: (c) => formatInt(m.per_class[c]?.support ?? 0) },
        ]}
      />
      <Text size="xs" c="dimmed" mt={4}>Precision: of the records predicted as this class, the share that truly had this label. Recall: of the records with this label, the share the model found.</Text>
      <Title order={3} size="h5" mt="md" mb="xs">Confusion matrix</Title>
      <ConfusionMatrix classes={classes} matrix={m.confusion_matrix} />
    </>
  );
}

export default function EvaluationPage() {
  const { bundle } = useModel();
  const [load, setLoad] = useState<Load>({ s: "loading" });
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let off = false;
    setLoad({ s: "loading" });
    getEvaluationReport()
      .then((raw) => {
        if (off) return;
        if (raw === null) return setLoad({ s: "none" });
        const c = checkReport(raw);
        setLoad(c.ok ? { s: "ok", report: c.report } : { s: "invalid", reason: c.reason });
      })
      .catch((e) => !off && setLoad({ s: "error", e: e as ApiError }));
    return () => { off = true; };
  }, [tick]);

  return (
    <>
      <PageHeader title="Model evaluation"
        intro="Results from the saved research test run on held-out motors. They are not recalculated from files you upload here, because an uploaded file has no verified labels." />
      {load.s === "loading" && <LoadingBlock label="Loading saved evaluation report…" />}
      {load.s === "error" && <ErrorState error={load.e} onRetry={() => setTick((t) => t + 1)} title="Could not load the evaluation report" />}
      {load.s === "none" && (
        <EmptyState title="No evaluation report has been saved for this site">
          After training, create it from the model bundle and rebuild or restart the frontend:
          <pre style={{ whiteSpace: "pre-wrap" }}><Code block>python ml/scripts/export_evaluation_report.py ml/artifacts/&lt;your bundle folder&gt; --data-origin real</Code></pre>
          No numbers are shown until a report exists.
        </EmptyState>
      )}
      {load.s === "invalid" && <Alert color="red" variant="light" title="The saved report cannot be used" role="alert">{load.reason} No numbers are shown.</Alert>}
      {load.s === "ok" && (() => {
        const r = load.report;
        const mismatch = bundle && r.bundle_version && bundle.bundle_version !== r.bundle_version;
        return (
          <div style={{ display: "grid", gap: 16 }}>
            <OriginNotice report={r} />
            {mismatch && <Alert color="yellow" variant="light" title="Different model version">This report is for model {r.bundle_version}, but the backend has {bundle!.bundle_version} loaded.</Alert>}
            <div className="panel">
              <Title order={2} size="h4" mb="xs">About this evaluation</Title>
              <dl style={{ display: "grid", gridTemplateColumns: "max-content 1fr", gap: "4px 16px", margin: 0 }}>
                <dt>Model version</dt><dd style={{ margin: 0 }}>{r.bundle_version ?? "Not recorded"}</dd>
                <dt>Task</dt><dd style={{ margin: 0 }}>{r.task ?? "Not recorded"}</dd>
                <dt>Test run on</dt><dd style={{ margin: 0 }}>{r.test_evaluated_at_utc ?? "Not recorded"}</dd>
                <dt>Dataset file</dt><dd style={{ margin: 0 }}>{r.dataset.file_name ?? "Not recorded"}</dd>
                <dt>Dataset size</dt><dd style={{ margin: 0 }}>{r.dataset.records != null ? `${formatInt(r.dataset.records)} records` : "Not recorded"}{r.dataset.motors != null ? `, ${formatInt(r.dataset.motors)} motors` : ""}</dd>
                <dt>Data origin</dt><dd style={{ margin: 0 }}>{r.data_origin}</dd>
                <dt>Split</dt><dd style={{ margin: 0 }}>{r.split_strategy ?? "Not recorded"}{r.split ? ` (${Object.entries(r.split).map(([k, v]) => `${k}: ${v.motors} motors, ${v.records} records`).join("; ")})` : ""}</dd>
              </dl>
            </div>
            <section aria-labelledby="ann"><Title order={2} size="h4" id="ann" mb="xs">Neural network (the deployed model)</Title><Metrics m={r.model} classes={r.classes} /></section>
            {Object.keys(r.baselines).length > 0 && (
              <section aria-labelledby="bl">
                <Title order={2} size="h4" id="bl" mb="xs">Baseline models on the same test set</Title>
                <DataTable
                  caption="Simple reference models trained on the same data. They are not deployed."
                  rows={Object.entries(r.baselines)} rowKey={([n]) => n}
                  columns={[
                    { key: "n", header: "Model", render: ([n]) => n },
                    { key: "a", header: "Accuracy", numeric: true, render: ([, m]) => formatMetric(m.accuracy) },
                    { key: "b", header: "Balanced accuracy", numeric: true, render: ([, m]) => formatMetric(m.balanced_accuracy) },
                    { key: "f", header: "Macro F1", numeric: true, render: ([, m]) => formatMetric(m.macro_f1) },
                    ...r.classes.map((c) => ({ key: `r-${c}`, header: `${c} recall`, numeric: true, render: ([, m]: [string, ModelMetrics]) => formatMetric(m.per_class[c]?.recall) })),
                  ]}
                />
              </section>
            )}
            <Text size="xs" c="dimmed">Source: {r.source}.</Text>
          </div>
        );
      })()}
    </>
  );
}
