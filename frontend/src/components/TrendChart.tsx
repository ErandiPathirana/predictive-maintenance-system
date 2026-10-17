import { Checkbox, Group, Switch, Text } from "@mantine/core";
import { useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { MEASURES, POSITIONS, SERIES_COLORS, SERIES_DASH, type MeasureKey, type PositionKey, type TrendData } from "../lib/trends";
import { DataTable } from "./DataTable";

type Measure = (typeof MEASURES)[number];

const p2 = (n: number) => String(n).padStart(2, "0");
/** Timestamps are parsed as local time (they carry no zone), so they must be formatted with LOCAL getters or they would shift. */
const stamp = (v: number, withTime: boolean) => {
  const d = new Date(v);
  const day = `${d.getFullYear()}-${p2(d.getMonth() + 1)}-${p2(d.getDate())}`;
  return withTime ? `${day} ${p2(d.getHours())}:${p2(d.getMinutes())}` : day;
};
const fmtX = (mode: TrendData["mode"], spanMs: number) => (v: number) =>
  mode === "sequence" ? String(v) : spanMs > 3 * 86_400_000 ? stamp(v, false).slice(5) : stamp(v, true).slice(5);

function Tip({ active, payload, label, mode, unit, measure }: {
  active?: boolean; payload?: ReadonlyArray<{ dataKey?: unknown; value?: unknown; color?: string }>; label?: unknown; mode: TrendData["mode"]; unit: string; measure: Measure;
}) {
  if (!active || !payload?.length) return null;
  const when = mode === "sequence" ? `Record ${label}` : stamp(Number(label), true);
  return (
    <div className="chart-tip">
      <p>{when}</p>
      {POSITIONS.map((p) => {
        const item = payload.find((i) => i.dataKey === `${p.key}_${measure.suffix}`);
        if (!item) return null;
        return <div key={p.key}><span style={{ color: SERIES_COLORS[p.key] }}>●</span>{p.short}: {typeof item.value === "number" ? `${item.value.toFixed(2)} ${unit}` : "no reading"}</div>;
      })}
    </div>
  );
}

/** One measure (velocity, gE or temperature) at the four bearing positions on a single axis. Legend, table view, missing-data note included. */
export function TrendChart({ data, measure, unit }: { data: TrendData; measure: Measure; unit?: string }) {
  const u = unit ?? measure.unit;
  const [shown, setShown] = useState<Record<PositionKey, boolean>>({ de_h: true, de_v: true, nde_h: true, nde_v: true });
  const [asTable, setAsTable] = useState(false);
  const cols = POSITIONS.map((p) => ({ ...p, col: `${p.key}_${measure.suffix}` }));
  const missingTotal = cols.reduce((s, c) => s + (data.missing[c.col] ?? 0), 0);
  const summary = `${measure.title} at four bearing positions, ${data.points.length} readings.`;
  const sparse = data.points.length <= 60;
  const span = data.points.length ? data.points[data.points.length - 1].x - data.points[0].x : 0;

  return (
    <section className="panel" aria-labelledby={`h-${measure.key}`}>
      <Group justify="space-between" align="flex-start" wrap="wrap" mb={4}>
        <div>
          <h2 id={`h-${measure.key}`} style={{ margin: 0, fontSize: "1.1rem" }}>{measure.title} ({u})</h2>
          <Text size="sm" c="dimmed" maw={640}>{measure.help}</Text>
        </div>
        <Switch label="Show as table" checked={asTable} onChange={(e) => setAsTable(e.currentTarget.checked)} />
      </Group>

      <Group gap="md" my="xs" role="group" aria-label={`Show or hide positions in ${measure.title}`}>
        {cols.map((c) => (
          <Checkbox
            key={c.key} size="xs" checked={shown[c.key]} onChange={(e) => setShown((s) => ({ ...s, [c.key]: e.currentTarget.checked }))}
            label={
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                <svg width="28" height="10" aria-hidden="true"><line x1="0" y1="5" x2="28" y2="5" stroke={SERIES_COLORS[c.key]} strokeWidth="3" strokeDasharray={SERIES_DASH[c.key]} /></svg>
                {c.short}
              </span>
            }
          />
        ))}
      </Group>

      {data.points.length === 0 ? (
        <Text size="sm" c="dimmed" py="lg">No readings in the selected period.</Text>
      ) : asTable ? (
        <DataTable
          caption={`${measure.title} (${u}). ${data.points.length > 200 ? "Showing the first 200 readings." : ""} Blank cells are missing readings.`}
          rows={data.points.slice(0, 200)}
          rowKey={(r) => r.x}
          columns={[
            { key: "t", header: data.mode === "time" ? "Time (as recorded)" : "Record order", render: (r) => (data.mode === "time" ? String(r.label).replace("T", " ").slice(0, 16) : String(r.x)) },
            ...cols.map((c) => ({ key: c.key, header: `${c.short} (${u})`, numeric: true, render: (r: { [k: string]: unknown }) => (typeof r[c.col] === "number" ? (r[c.col] as number).toFixed(2) : "") })),
          ]}
        />
      ) : (
        <div role="img" aria-label={summary} style={{ width: "100%", height: 280 }}>
          <ResponsiveContainer width="100%" height="100%" minWidth={0}>
            <LineChart data={data.points} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="x" type="number" scale={data.mode === "time" ? "time" : "linear"} domain={["dataMin", "dataMax"]} tickFormatter={fmtX(data.mode, span)} tickCount={5} minTickGap={24} />
              <YAxis width={52} tickFormatter={(v: number) => String(Math.round(v * 100) / 100)} label={{ value: u, angle: -90, position: "insideLeft", style: { textAnchor: "middle" } }} />
              <Tooltip content={<Tip mode={data.mode} unit={u} measure={measure} />} />
              {cols.map((c) =>
                shown[c.key] ? (
                  <Line key={c.key} type="monotone" dataKey={c.col} name={c.short} stroke={SERIES_COLORS[c.key]} strokeDasharray={SERIES_DASH[c.key]}
                    strokeWidth={2} dot={sparse ? { r: 3, strokeWidth: 0, fill: SERIES_COLORS[c.key] } : false} activeDot={{ r: 5 }} connectNulls={false} isAnimationActive={false} />
                ) : null,
              )}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
      <Text size="xs" c="dimmed" mt={6}>
        {missingTotal > 0
          ? `${missingTotal} reading${missingTotal === 1 ? " is" : "s are"} missing in the plotted records. Lines are broken where a reading is missing.`
          : "No missing readings in the plotted records."}
      </Text>
    </section>
  );
}

export type { MeasureKey };
