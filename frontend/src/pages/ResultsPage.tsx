import { Button, Group, Pagination, Select, Stack, Text, TextInput } from "@mantine/core";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ConditionBadge } from "../components/ConditionBadge";
import { DataTable } from "../components/DataTable";
import { ModelNotice, NotConfirmedStatement } from "../components/DemoNotice";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/StateViews";
import { useSession } from "../context/SessionContext";
import { CONDITION_ORDER, severityRank } from "../lib/condition";
import { formatInt, formatScore, formatTimestamp } from "../lib/format";
import type { PredictionResult } from "../types/api";

const PAGE_SIZE = 50;

export default function ResultsPage() {
  const { analysis } = useSession();
  const [motor, setMotor] = useState("");
  const [condition, setCondition] = useState<string | null>(null);
  const [onlyWarned, setOnlyWarned] = useState(false);
  const [page, setPage] = useState(1);

  const rows = useMemo(() => {
    if (!analysis) return [];
    return analysis.results
      .filter((r) => (!motor.trim() || (r.motor_id ?? "").toLowerCase().includes(motor.trim().toLowerCase())) && (!condition || r.predicted_condition === condition) && (!onlyWarned || r.input_warnings.length > 0))
      .sort((a, b) => severityRank(b.predicted_condition) - severityRank(a.predicted_condition));
  }, [analysis, motor, condition, onlyWarned]);

  if (!analysis) {
    return (
      <>
        <PageHeader title="Prediction results" />
        <EmptyState title="No analysis in this session" action={<Button component={Link} to="/upload" size="xs">Upload and analyse a file</Button>}>
          Results of the file you analyse appear here. Earlier predictions are always available in Prediction history.
        </EmptyState>
      </>
    );
  }
  const calibrated = analysis.results.some((r) => r.scores_are_calibrated_probabilities);
  const classNames = [...new Set(analysis.results.flatMap((r) => Object.keys(r.scores)))];
  const scoreLabel = calibrated ? "Probability" : "Model score";
  const pageCount = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const shown = rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const unconf = analysis.results.some((r) => r.demonstration_only || r.provisional_label_provenance);

  return (
    <>
      <PageHeader title="Prediction results"
        intro={<>Predicted condition for each record in <strong>{analysis.filename}</strong>. Most serious first.</>} />
      <Stack gap="sm">
        <div className="panel"><NotConfirmedStatement />
          <Text size="sm" c="dimmed" mt={4}>
            {calibrated ? "Scores are reported by the model as probabilities." : `${scoreLabel}s are raw outputs of the model for each class, between 0 and 1. They are not calibrated probabilities, so 0.80 does not mean an 80% chance.`}
            {" "}Model version {analysis.model_version}.{unconf && " This model is a demonstration with provisional training labels."}
          </Text>
        </div>
        <ModelNotice compact />
        <div className="panel">
          <Group align="flex-end" gap="md" wrap="wrap" role="search" aria-label="Filter results">
            <TextInput label="Motor ID contains" value={motor} onChange={(e) => { setMotor(e.currentTarget.value); setPage(1); }} w={200} />
            <Select label="Predicted condition" data={CONDITION_ORDER.map((c) => ({ value: c, label: c }))} value={condition} onChange={(v) => { setCondition(v); setPage(1); }} clearable placeholder="All" w={200} />
            <label style={{ display: "flex", gap: 8, alignItems: "center", paddingBottom: 8 }}>
              <input type="checkbox" checked={onlyWarned} onChange={(e) => { setOnlyWarned(e.target.checked); setPage(1); }} /> Only records with input warnings
            </label>
            <Button variant="default" onClick={() => { setMotor(""); setCondition(null); setOnlyWarned(false); setPage(1); }}>Clear filters</Button>
          </Group>
        </div>
        {rows.length === 0 ? (
          <EmptyState title="No records match these filters" />
        ) : (
          <>
            <DataTable<PredictionResult>
              caption={`${formatInt(rows.length)} of ${formatInt(analysis.results.length)} records. Page ${page} of ${pageCount}.`}
              rows={shown} rowKey={(r, i) => r.prediction_id ?? `${r.record_id}-${i}`}
              columns={[
                { key: "rec", header: "Record", render: (r) => r.record_id ?? "Not recorded" },
                { key: "mot", header: "Motor", render: (r) => r.motor_id ?? "Not recorded" },
                { key: "at", header: "Measured at", render: (r) => formatTimestamp(r.measured_at) },
                { key: "c", header: "Predicted condition", render: (r) => <ConditionBadge condition={r.predicted_condition} /> },
                ...classNames.map((c) => ({ key: `s-${c}`, header: `${scoreLabel}: ${c}`, numeric: true, render: (r: PredictionResult) => formatScore(r.scores[c]) })),
                { key: "w", header: "Input warnings", render: (r) => (r.input_warnings.length ? <details><summary>{r.input_warnings.length} warning{r.input_warnings.length > 1 ? "s" : ""}</summary><ul style={{ margin: 0, paddingLeft: 18 }}>{r.input_warnings.map((w) => <li key={w.feature}>{w.message}</li>)}</ul></details> : "None") },
                { key: "v", header: "Model version", render: (r) => r.model_version },
              ]}
            />
            {pageCount > 1 && <Pagination total={pageCount} value={page} onChange={setPage} aria-label="Result pages" />}
          </>
        )}
      </Stack>
    </>
  );
}
