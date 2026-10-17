import { Link } from "react-router-dom";
import { Anchor, Alert, Button, Group, SegmentedControl, Select, Stack, Text, TextInput } from "@mantine/core";
import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ApiError, downloadReport, getPredictions, saveFile } from "../api/client";
import { ConditionBadge } from "../components/ConditionBadge";
import { DataTable } from "../components/DataTable";
import { ModelNotice, NotConfirmedStatement } from "../components/DemoNotice";
import { PageHeader } from "../components/PageHeader";
import { EmptyState, ErrorState, LoadingBlock } from "../components/StateViews";
import { CONDITION_ORDER } from "../lib/condition";
import { formatInt, formatScore, formatTimestamp } from "../lib/format";
import { topScore } from "../lib/aggregate";
import type { HistoryFilters, PredictionPage } from "../types/api";

const LIMIT = 50;
type DateBasis = "measured" | "stored";

interface FormState { motor: string; condition: string | null; from: string; to: string; basis: DateBasis }

function toFilters(f: FormState): HistoryFilters {
  const out: HistoryFilters = {};
  if (f.motor.trim()) out.motor_id = f.motor.trim();
  if (f.condition) out.predicted_condition = f.condition;
  if (f.basis === "measured") { if (f.from) out.measured_from = f.from; if (f.to) out.measured_to = f.to; }
  else { if (f.from) out.date_from = f.from; if (f.to) out.date_to = f.to; }
  return out;
}

export default function HistoryPage() {
  const [params] = useSearchParams();
  const [form, setForm] = useState<FormState>({ motor: params.get("motor_id") ?? "", condition: null, from: "", to: "", basis: "measured" });
  const [applied, setApplied] = useState<HistoryFilters>(() => toFilters({ motor: params.get("motor_id") ?? "", condition: null, from: "", to: "", basis: "measured" }));
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<PredictionPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | Error | null>(null);
  const [exportMsg, setExportMsg] = useState<{ tone: "info" | "warn"; text: string } | null>(null);
  const [exporting, setExporting] = useState(false);
  const [tick, setTick] = useState(0);
  const rangeBad = !!form.from && !!form.to && form.from > form.to;

  useEffect(() => {
    let cancelled = false;
    setLoading(true); setError(null);
    getPredictions(applied, LIMIT, offset)
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e) => { if (!cancelled) setError(e); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [applied, offset, tick]);

  const apply = (e: React.FormEvent) => { e.preventDefault(); if (rangeBad) return; setOffset(0); setApplied(toFilters(form)); setExportMsg(null); };
  const reset = () => { const f: FormState = { motor: "", condition: null, from: "", to: "", basis: "measured" }; setForm(f); setOffset(0); setApplied({}); setExportMsg(null); };

  const doExport = useCallback(async () => {
    setExporting(true); setExportMsg(null);
    try {
      const file = await downloadReport(applied);
      saveFile(file);
      setExportMsg(file.truncated
        ? { tone: "warn", text: `Only the first ${formatInt(file.rowsExported ?? 0)} of ${formatInt(file.totalMatching ?? 0)} matching rows were exported (server limit). Narrow the filters and export again.` }
        : { tone: "info", text: `Exported ${formatInt(file.rowsExported ?? 0)} rows to ${file.filename}.` });
    } catch (e) { setError(e as ApiError); } finally { setExporting(false); }
  }, [applied]);

  const page = data ? Math.floor(data.offset / data.limit) + 1 : 1;
  const pages = data ? Math.max(1, Math.ceil(data.total / data.limit)) : 1;

  return (
    <>
      <PageHeader title="Assessment history" intro="Every saved assessment, newest first. Open one to see its recommended next steps. Raw sensor readings are not stored unless the server is set to keep them." />
      <Stack gap="sm">
        <ModelNotice compact />
        <form className="panel" onSubmit={apply} aria-label="Filter history">
          <Group align="flex-end" gap="md" wrap="wrap">
            <TextInput label="Motor ID" value={form.motor} onChange={(e) => setForm({ ...form, motor: e.currentTarget.value })} w={170} maxLength={64} />
            <Select label="Predicted condition" data={CONDITION_ORDER.map((c) => ({ value: c, label: c }))} value={form.condition} onChange={(v) => setForm({ ...form, condition: v })} clearable placeholder="All" w={180} />
            <div>
              <Text size="sm" fw={500} id="basis-label">Dates refer to</Text>
              <SegmentedControl aria-labelledby="basis-label" data={[{ value: "measured", label: "Measurement time" }, { value: "stored", label: "Time analysed" }]} value={form.basis} onChange={(v) => setForm({ ...form, basis: v as DateBasis })} />
            </div>
            <label style={{ display: "flex", flexDirection: "column", fontSize: 14, fontWeight: 500, gap: 4 }}>From
              <input type="date" value={form.from} onChange={(e) => setForm({ ...form, from: e.target.value })} style={{ padding: "7px 8px", border: "1px solid var(--border)", borderRadius: 4 }} />
            </label>
            <label style={{ display: "flex", flexDirection: "column", fontSize: 14, fontWeight: 500, gap: 4 }}>To
              <input type="date" value={form.to} onChange={(e) => setForm({ ...form, to: e.target.value })} style={{ padding: "7px 8px", border: "1px solid var(--border)", borderRadius: 4 }} />
            </label>
            <Button type="submit" disabled={rangeBad}>Apply filters</Button>
            <Button variant="default" onClick={reset}>Clear</Button>
          </Group>
          {rangeBad && <Text c="red.8" size="sm" mt="xs" role="alert">The "From" date is after the "To" date.</Text>}
        </form>

        {error && <ErrorState error={error} onRetry={() => { setError(null); setTick((t) => t + 1); }} title="Could not load or export history" />}
        {loading && <LoadingBlock label="Loading history…" />}
        {!loading && data && data.total === 0 && (
          <EmptyState title={Object.keys(applied).length ? "No stored predictions match these filters" : "No predictions stored yet"}>
            {Object.keys(applied).length ? "Try widening the dates or clearing the filters." : <>Analyse a file on the <Anchor href="#/upload">Upload page</Anchor> and its predictions will be listed here.</>}
          </EmptyState>
        )}
        {data && data.total > 0 && (
          <>
            <Group justify="space-between" wrap="wrap">
              <Text size="sm" role="status" aria-live="polite">{formatInt(data.total)} matching prediction{data.total === 1 ? "" : "s"}. Showing {formatInt(data.offset + 1)} to {formatInt(data.offset + data.items.length)}.</Text>
              <Button variant="default" onClick={doExport} loading={exporting}>Export matching rows (CSV)</Button>
            </Group>
            {exportMsg && <Alert color={exportMsg.tone === "warn" ? "yellow" : "green"} variant="light" role="status">{exportMsg.text}</Alert>}
            <NotConfirmedStatement />
            <DataTable
              caption="Stored predictions, newest first"
              rows={data.items} rowKey={(r) => r.id}
              columns={[
                { key: "id", header: "ID", numeric: true, render: (r) => <Anchor component={Link} to={`/assessment/${r.id}`} aria-label={`Open assessment ${r.id}`}>{r.id}</Anchor> },
                { key: "m", header: "Motor", render: (r) => r.motor_id ?? "Not recorded" },
                { key: "r", header: "Record", render: (r) => r.record_id ?? "Not recorded" },
                { key: "at", header: "Measured at", render: (r) => formatTimestamp(r.measured_at) },
                { key: "c", header: "Predicted condition", render: (r) => <ConditionBadge condition={r.predicted_condition} /> },
                { key: "rec", header: "Recommended next step", render: (r) => r.recommendation_summary ?? <Text size="sm" c="dimmed" component="span">Open the record to see the steps</Text> },
                { key: "s", header: "Model score (predicted class)", numeric: true, render: (r) => formatScore(topScore(r)) },
                { key: "st", header: "Analysed (UTC)", render: (r) => formatTimestamp(r.created_at) },
                { key: "v", header: "Model version", render: (r) => r.model_version },
                { key: "f", header: "Label status", render: (r) => [r.demonstration_only ? "Demonstration" : null, r.provisional_label_provenance ? "Provisional labels" : null].filter(Boolean).join(", ") || "No flags" },
              ]}
            />
            <Group justify="space-between">
              <Button variant="default" disabled={page <= 1 || loading} onClick={() => setOffset(Math.max(0, offset - LIMIT))}>Previous page</Button>
              <Text size="sm">Page {page} of {pages}</Text>
              <Button variant="default" disabled={page >= pages || loading} onClick={() => setOffset(offset + LIMIT)}>Next page</Button>
            </Group>
          </>
        )}
      </Stack>
    </>
  );
}
