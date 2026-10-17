import { sortableTime } from "./format";

export const POSITIONS = [
  { key: "de_h", label: "Drive end, horizontal", short: "DE horizontal" },
  { key: "de_v", label: "Drive end, vertical", short: "DE vertical" },
  { key: "nde_h", label: "Non-drive end, horizontal", short: "NDE horizontal" },
  { key: "nde_v", label: "Non-drive end, vertical", short: "NDE vertical" },
] as const;

export const MEASURES = [
  { key: "velocity", suffix: "velocity_mm_s", title: "Vibration velocity", unit: "mm/s",
    help: "Vibration velocity at the four bearing positions. The kind of velocity (RMS, peak) is not stated in the source data." },
  { key: "ge", suffix: "ge", title: "Bearing condition", unit: "gE",
    help: "gE is the enveloped-acceleration reading in the data. Its exact definition is not stated in the source data." },
  { key: "temp", suffix: "temp_c", title: "Temperature", unit: "°C", help: "Surface temperature at the four bearing positions." },
] as const;

export type MeasureKey = (typeof MEASURES)[number]["key"];
export type PositionKey = (typeof POSITIONS)[number]["key"];

/** Fixed order so a position keeps its colour in every chart (blue, orange, aqua, yellow). */
export const SERIES_COLORS: Record<PositionKey, string> = {
  de_h: "var(--series-1)", de_v: "var(--series-2)", nde_h: "var(--series-3)", nde_v: "var(--series-4)",
};
export const SERIES_DASH: Record<PositionKey, string | undefined> = { de_h: undefined, de_v: "6 3", nde_h: "2 3", nde_v: "10 3 2 3" };

export interface TrendPoint {
  /** time in ms, or the 1-based record order in "sequence" mode */
  x: number;
  label: string;
  [column: string]: number | string | null;
}

export interface TrendData {
  mode: "time" | "sequence";
  points: TrendPoint[];
  totalRows: number;
  /** rows left out because they have no usable timestamp (time mode only) */
  withoutTimestamp: number;
  /** per column: how many of the plotted rows have no usable number */
  missing: Record<string, number>;
}

const num = (v: string | undefined): number | null => {
  if (v === undefined || v.trim() === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
};

export const dateOnly = (v: string | undefined): string => (v ?? "").slice(0, 10);

export function buildTrend(rows: Record<string, string>[], motorId: string, range: { from?: string; to?: string }): TrendData {
  const mine = rows.filter((r) => (r.motor_id ?? "").trim() === motorId);
  const timed = mine.filter((r) => !Number.isNaN(sortableTime(r.measured_at)));
  const mode: TrendData["mode"] = timed.length > 0 ? "time" : "sequence";
  let pool = mode === "time" ? timed : mine;
  if (mode === "time") {
    if (range.from) pool = pool.filter((r) => dateOnly(r.measured_at) >= range.from!);
    if (range.to) pool = pool.filter((r) => dateOnly(r.measured_at) <= range.to!);
  }
  const columns = MEASURES.flatMap((m) => POSITIONS.map((p) => `${p.key}_${m.suffix}`));
  const points: TrendPoint[] = pool.map((r, i) => {
    const pt: TrendPoint = {
      x: mode === "time" ? sortableTime(r.measured_at) : i + 1,
      label: mode === "time" ? (r.measured_at ?? "") : `Record ${i + 1}`,
      record_id: r.record_id ?? null,
    };
    for (const c of columns) pt[c] = num(r[c]);
    return pt;
  });
  points.sort((a, b) => a.x - b.x);
  const missing = Object.fromEntries(columns.map((c) => [c, points.filter((p) => p[c] === null).length]));
  return { mode, points, totalRows: mine.length, withoutTimestamp: mode === "time" ? mine.length - timed.length : 0, missing };
}

export function motorIdsIn(rows: Record<string, string>[]): string[] {
  return [...new Set(rows.map((r) => (r.motor_id ?? "").trim()).filter(Boolean))].sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
}
