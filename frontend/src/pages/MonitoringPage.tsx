import { Button, Group, Select, Stack, Text } from "@mantine/core";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ConditionBadge } from "../components/ConditionBadge";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/StateViews";
import { TrendChart } from "../components/TrendChart";
import { useModel } from "../context/ModelContext";
import { useSession } from "../context/SessionContext";
import { formatInt } from "../lib/format";
import { MEASURES, buildTrend, dateOnly, motorIdsIn } from "../lib/trends";

export default function MonitoringPage() {
  const { dataset, analysis } = useSession();
  const { features } = useModel();
  const motors = useMemo(() => (dataset ? motorIdsIn(dataset.rows) : []), [dataset]);
  const [motor, setMotor] = useState<string | null>(null);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");

  useEffect(() => { if (motors.length && (!motor || !motors.includes(motor))) setMotor(motors[0]); }, [motors, motor]);

  const trend = useMemo(() => (dataset && motor ? buildTrend(dataset.rows, motor, { from: from || undefined, to: to || undefined }) : null), [dataset, motor, from, to]);
  const rangeBad = from && to && from > to;
  const unitOf = (suffix: string) => features.find((f) => f.name.endsWith(suffix))?.unit ?? undefined;

  const dates = useMemo(() => {
    if (!dataset || !motor) return null;
    const d = dataset.rows.filter((r) => r.motor_id?.trim() === motor).map((r) => dateOnly(r.measured_at)).filter((x) => /^\d{4}-\d{2}-\d{2}$/.test(x)).sort();
    return d.length ? { min: d[0], max: d[d.length - 1] } : null;
  }, [dataset, motor]);

  const latestResult = useMemo(() => {
    if (!analysis || !motor) return null;
    const mine = analysis.results.filter((r) => r.motor_id === motor && r.measured_at);
    if (!mine.length) return null;
    return mine.reduce((a, b) => (String(b.measured_at) > String(a.measured_at) ? b : a));
  }, [analysis, motor]);

  return (
    <>
      <PageHeader title="Motor monitoring"
        intro="Sensor trends for one motor, taken from the file you loaded on the Upload page. The server does not keep raw sensor readings, so nothing can be shown here until a file is loaded in this browser tab." />
      {!dataset ? (
        <EmptyState title="No sensor file loaded" action={<Button component={Link} to="/upload" size="xs">Go to Upload and analyse</Button>}>
          Choose a CSV file there. It is read in your browser and kept only until you reload or close this tab.
        </EmptyState>
      ) : motors.length === 0 ? (
        <EmptyState title="The loaded file has no motor IDs">Each row needs a value in the motor_id column to be grouped by motor.</EmptyState>
      ) : (
        <Stack gap="md">
          <div className="panel">
            <Group align="flex-end" gap="md" wrap="wrap">
              <Select label="Motor" data={motors} value={motor} onChange={setMotor} allowDeselect={false} searchable w={220} />
              <label style={{ display: "flex", flexDirection: "column", fontSize: 14, fontWeight: 500, gap: 4 }}>
                From date
                <input type="date" value={from} min={dates?.min} max={dates?.max} onChange={(e) => setFrom(e.target.value)} style={{ padding: "7px 8px", border: "1px solid var(--border)", borderRadius: 4 }} />
              </label>
              <label style={{ display: "flex", flexDirection: "column", fontSize: 14, fontWeight: 500, gap: 4 }}>
                To date
                <input type="date" value={to} min={dates?.min} max={dates?.max} onChange={(e) => setTo(e.target.value)} style={{ padding: "7px 8px", border: "1px solid var(--border)", borderRadius: 4 }} />
              </label>
              <Button variant="default" onClick={() => { setFrom(""); setTo(""); }} disabled={!from && !to}>Show all dates</Button>
            </Group>
            {rangeBad && <Text c="red.8" size="sm" mt="xs" role="alert">The "From" date is after the "To" date. Swap them to see readings.</Text>}
            <Text size="sm" c="dimmed" mt="sm">
              {trend && (
                <>
                  {formatInt(trend.points.length)} of {formatInt(trend.totalRows)} readings shown for motor {motor}.
                  {trend.mode === "sequence" && " This file has no usable measurement times, so readings are plotted in file order."}
                  {trend.withoutTimestamp > 0 && ` ${formatInt(trend.withoutTimestamp)} reading(s) have no usable timestamp and are left out of the charts.`}
                </>
              )}
            </Text>
            {latestResult && (
              <Group gap="xs" mt="xs">
                <Text size="sm">Latest predicted condition in the analysed file:</Text>
                <ConditionBadge condition={latestResult.predicted_condition} />
                <Text size="sm" c="dimmed">(an estimate, not a confirmed failure)</Text>
              </Group>
            )}
          </div>
          {trend && !rangeBad && MEASURES.map((m) => <TrendChart key={m.key} data={trend} measure={m} unit={unitOf(m.suffix)} />)}
        </Stack>
      )}
    </>
  );
}
