import { Anchor, Button, Group, SimpleGrid, Text, Title } from "@mantine/core";
import { Link } from "react-router-dom";
import { ConditionBadge } from "../components/ConditionBadge";
import { DataTable } from "../components/DataTable";
import { ModelNotice, NotConfirmedStatement } from "../components/DemoNotice";
import { PageHeader } from "../components/PageHeader";
import { StatCard } from "../components/StatCard";
import { EmptyState, ErrorState, LoadingBlock } from "../components/StateViews";
import { useSession } from "../context/SessionContext";
import { useAllPredictions } from "../hooks/useAllPredictions";
import { countConditions, latestPerMotor, recentActivity, topScore } from "../lib/aggregate";
import { CONDITION_ORDER } from "../lib/condition";
import { formatInt, formatScore, formatTimestamp } from "../lib/format";
import { MEASURES, POSITIONS } from "../lib/trends";

function SensorSummary() {
  const { dataset } = useSession();
  if (!dataset) {
    return (
      <EmptyState title="No sensor file loaded in this browser session"
        action={<Button component={Link} to="/upload" size="xs" variant="default">Upload a file</Button>}>
        The server does not store raw sensor readings by default. A trend summary appears here after you load a CSV file on the Upload page.
        The file stays in this browser tab only.
      </EmptyState>
    );
  }
  const stats = MEASURES.flatMap((m) =>
    POSITIONS.map((p) => {
      const col = `${p.key}_${m.suffix}`;
      const v = dataset.rows.map((r) => (r[col]?.trim() === "" ? NaN : Number(r[col]))).filter((n) => Number.isFinite(n));
      return { id: col, measure: `${m.title} (${m.unit})`, position: p.short, n: v.length, min: Math.min(...v), mean: v.reduce((a, b) => a + b, 0) / (v.length || 1), max: Math.max(...v) };
    }),
  );
  const f = (n: number, has: boolean) => (has ? n.toFixed(2) : "n/a");
  return (
    <>
      <Text size="sm" c="dimmed" mb="xs">From <strong>{dataset.fileName}</strong> ({formatInt(dataset.rows.length)} rows), loaded in this session. Open Motor monitoring for the charts.</Text>
      <DataTable
        caption="Sensor summary of the loaded file: lowest, average and highest reading per bearing position"
        rows={stats} rowKey={(r) => r.id}
        columns={[
          { key: "m", header: "Measurement", render: (r) => r.measure },
          { key: "p", header: "Position", render: (r) => r.position },
          { key: "n", header: "Readings", numeric: true, render: (r) => formatInt(r.n) },
          { key: "min", header: "Lowest", numeric: true, render: (r) => f(r.min, r.n > 0) },
          { key: "mean", header: "Average", numeric: true, render: (r) => f(r.mean, r.n > 0) },
          { key: "max", header: "Highest", numeric: true, render: (r) => f(r.max, r.n > 0) },
        ]}
      />
    </>
  );
}

export default function DashboardPage() {
  const all = useAllPredictions();
  const latest = latestPerMotor(all.items);
  const counts = countConditions(latest.map((l) => l.item.predicted_condition));
  const recent = recentActivity(all.items, 8);
  const storedBasis = latest.some((l) => l.basis === "stored_at");

  return (
    <>
      <PageHeader title="Dashboard" intro="The most recent predicted condition of every motor that has stored predictions.">
        <Group mt={6}><Button component={Link} to="/assess">New motor assessment</Button></Group>
      </PageHeader>
      <ModelNotice compact />
      <div style={{ height: 12 }} />
      {all.loading ? (
        <LoadingBlock label="Loading stored predictions…" />
      ) : all.error ? (
        <ErrorState error={all.error} onRetry={all.reload} title="Could not load the dashboard" />
      ) : all.total === 0 ? (
        <EmptyState title="No predictions stored yet"
          action={<Button component={Link} to="/upload" size="xs">Upload and analyse a CSV file</Button>}>
          Once you analyse a file, each motor's latest predicted condition and recent activity appear here.
        </EmptyState>
      ) : (
        <>
          {all.truncated && (
            <Text size="sm" c="dimmed" mb="sm" role="note">
              The server holds {formatInt(all.total)} stored predictions. This page summarises the newest {formatInt(all.items.length)}. Use Assessment history for all of them.
            </Text>
          )}
          <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="sm" mb="md">
            <StatCard label="Distinct motors" value={formatInt(latest.length)} />
            {CONDITION_ORDER.map((c) => (
              <StatCard key={c} label={`Motors latest ${c}`} value={formatInt(counts[c] ?? 0)} note={<ConditionBadge condition={c} />} />
            ))}
          </SimpleGrid>
          <div style={{ marginBottom: 12 }}><NotConfirmedStatement /></div>

          <Title order={2} size="h4" mb="xs">Latest condition per motor</Title>
          <Text size="sm" c="dimmed" mb="xs">
            "Latest" means the newest <em>measurement time</em> in the data, not the order of upload.
            {storedBasis && " Some motors have no measurement times, so for those the time the prediction was stored is used (marked with *)."}
          </Text>
          <DataTable
            caption={`${latest.length} motors, latest predicted condition each`}
            rows={latest} rowKey={(r) => r.motorId}
            columns={[
              { key: "m", header: "Motor", render: (r) => <Anchor component={Link} to={`/history?motor_id=${encodeURIComponent(r.motorId)}`}>{r.motorId}</Anchor> },
              { key: "c", header: "Predicted condition", render: (r) => <ConditionBadge condition={r.item.predicted_condition} /> },
              { key: "t", header: "Measured at", render: (r) => (r.basis === "measured_at" ? formatTimestamp(r.item.measured_at) : `${formatTimestamp(r.item.created_at)} *`) },
              { key: "s", header: "Model score", numeric: true, render: (r) => formatScore(topScore(r.item)) },
              { key: "n", header: "Records", numeric: true, render: (r) => formatInt(r.recordCount) },
            ]}
          />
          <Text size="xs" c="dimmed" mt={4}>Model score is the model's output for the predicted class. It is not a calibrated probability.</Text>

          <Title order={2} size="h4" mt="lg" mb="xs">Recent activity</Title>
          <DataTable
            caption="Most recently stored predictions"
            rows={recent} rowKey={(r) => r.id}
            columns={[
              { key: "w", header: "Stored at (UTC)", render: (r) => formatTimestamp(r.created_at) },
              { key: "m", header: "Motor", render: (r) => r.motor_id ?? "Not recorded" },
              { key: "c", header: "Predicted condition", render: (r) => <ConditionBadge condition={r.predicted_condition} /> },
              { key: "src", header: "Source", render: (r) => (r.source === "csv" ? "CSV upload" : "Manual entry") },
            ]}
          />
          <Group mt="xs"><Anchor component={Link} to="/history" size="sm">Open full history</Anchor></Group>
        </>
      )}

      <Title order={2} size="h4" mt="lg" mb="xs">Sensor trend summary</Title>
      <SensorSummary />
    </>
  );
}
