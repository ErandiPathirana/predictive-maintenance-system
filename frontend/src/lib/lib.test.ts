import { countConditions, latestPerMotor, NO_MOTOR, recentActivity } from "./aggregate";
import { conditionMeta, severityRank } from "./condition";
import { missingColumns, quickFileCheck } from "./csvFile";
import { checkReport } from "./evaluation";
import { formatTimestamp, safeCell, sortableTime } from "./format";
import { buildTrend, motorIdsIn } from "./trends";
import type { HistoryItem } from "../types/api";

const item = (o: Partial<HistoryItem>): HistoryItem => ({
  id: 1, batch_id: null, source: "csv", record_id: "r", motor_id: "A", measured_at: null, created_at: "2026-01-01T00:00:00",
  predicted_condition: "Normal", predicted_class_id: 0, scores: { Normal: 0.9 }, model_version: "v", provisional_label_provenance: true, demonstration_only: true, ...o,
});

describe("latestPerMotor", () => {
  it("uses the measurement time, not the upload order or row id", () => {
    const rows = [
      item({ id: 1, measured_at: "2025-06-01T10:00:00", predicted_condition: "Danger" }),
      item({ id: 2, measured_at: "2025-01-01T10:00:00", predicted_condition: "Normal" }), // stored later, measured earlier
    ];
    const [m] = latestPerMotor(rows);
    expect(m.item.predicted_condition).toBe("Danger");
    expect(m.basis).toBe("measured_at");
    expect(m.recordCount).toBe(2);
  });
  it("falls back to the stored time only when a motor has no measurement times, and says so", () => {
    const rows = [item({ id: 1, created_at: "2026-02-01T00:00:00" }), item({ id: 2, created_at: "2026-03-01T00:00:00", predicted_condition: "Alert" })];
    const [m] = latestPerMotor(rows);
    expect(m.item.predicted_condition).toBe("Alert");
    expect(m.basis).toBe("stored_at");
  });
  it("ignores rows without a timestamp when the motor has timestamped rows", () => {
    const [m] = latestPerMotor([item({ id: 9, measured_at: null, created_at: "2030-01-01T00:00:00", predicted_condition: "Danger" }), item({ id: 1, measured_at: "2025-01-01T00:00:00" })]);
    expect(m.item.id).toBe(1);
  });
  it("groups missing motor ids together and sorts motors naturally", () => {
    const out = latestPerMotor([item({ motor_id: "M10" }), item({ motor_id: "M2" }), item({ motor_id: null })]);
    expect(out.map((o) => o.motorId)).toEqual([NO_MOTOR, "M2", "M10"]);
  });
});

describe("counts and activity", () => {
  it("always reports the three classes, even at zero", () => {
    expect(countConditions(["Alert", "Alert"])).toEqual({ Normal: 0, Alert: 2, Danger: 0 });
  });
  it("orders recent activity newest first", () => {
    const r = recentActivity([item({ id: 1, created_at: "2026-01-01T00:00:00" }), item({ id: 2, created_at: "2026-02-01T00:00:00" })], 1);
    expect(r[0].id).toBe(2);
  });
});

describe("condition and format helpers", () => {
  it("ranks severity and knows unknown classes", () => {
    expect(severityRank("Danger")).toBeGreaterThan(severityRank("Alert"));
    expect(conditionMeta("Weird").label).toBe("Weird");
  });
  it("shows timestamps as recorded, without shifting time zones", () => {
    expect(formatTimestamp("2025-04-01T07:20:00")).toBe("2025-04-01 07:20");
    expect(formatTimestamp(null)).toBe("Not recorded");
    expect(Number.isNaN(sortableTime("garbage"))).toBe(true);
  });
  it("neutralises spreadsheet formulas", () => {
    expect(safeCell("=SUM(A1)")).toBe("'=SUM(A1)");
    expect(safeCell("MOT1")).toBe("MOT1");
  });
});

describe("csv checks", () => {
  it("rejects wrong type, empty and oversized files", () => {
    expect(quickFileCheck(new File(["x"], "a.txt"))).toMatch(/\.csv/);
    expect(quickFileCheck(new File([], "a.csv"))).toMatch(/empty/);
    expect(quickFileCheck(new File([new Uint8Array(2_000_001)], "a.csv"))).toMatch(/MB/);
    expect(quickFileCheck(new File(["a"], "a.csv"))).toBeNull();
  });
  it("lists the required columns that are missing", () => {
    expect(missingColumns(["record_id", "x"], ["x", "y"])).toEqual(["motor_id", "y"]);
  });
});

describe("buildTrend", () => {
  const rows: Record<string, string>[] = [
    { motor_id: "A", measured_at: "2025-01-02 00:00:00", record_id: "2", de_h_velocity_mm_s: "3", de_v_velocity_mm_s: "" },
    { motor_id: "A", measured_at: "2025-01-01 00:00:00", record_id: "1", de_h_velocity_mm_s: "2", de_v_velocity_mm_s: "abc" },
    { motor_id: "A", measured_at: "", record_id: "3", de_h_velocity_mm_s: "9" },
    { motor_id: "B", measured_at: "2025-01-01 00:00:00", record_id: "4", de_h_velocity_mm_s: "1" },
  ];
  it("sorts by time, counts missing values and rows without timestamps", () => {
    const t = buildTrend(rows, "A", {});
    expect(t.mode).toBe("time");
    expect(t.points.map((p) => p.record_id)).toEqual(["1", "2"]);
    expect(t.withoutTimestamp).toBe(1);
    expect(t.missing.de_v_velocity_mm_s).toBe(2);
    expect(t.missing.de_h_velocity_mm_s).toBe(0);
    expect(t.points[0].de_v_velocity_mm_s).toBeNull();
  });
  it("filters by inclusive date range", () => {
    expect(buildTrend(rows, "A", { from: "2025-01-02" }).points).toHaveLength(1);
    expect(buildTrend(rows, "A", { to: "2025-01-01" }).points).toHaveLength(1);
    expect(buildTrend(rows, "A", { from: "2025-02-01" }).points).toHaveLength(0);
  });
  it("uses file order when no row has a timestamp", () => {
    const t = buildTrend([{ motor_id: "A", record_id: "1", de_h_velocity_mm_s: "1" }], "A", {});
    expect(t.mode).toBe("sequence");
    expect(t.points).toHaveLength(1);
  });
  it("lists motors", () => expect(motorIdsIn(rows)).toEqual(["A", "B"]));
});

describe("checkReport", () => {
  const good = {
    schema: "pm.evaluation_report.v1", classes: ["Normal", "Alert", "Danger"], baselines: {},
    model: { n: 3, per_class: { Normal: { recall: 1 }, Alert: { recall: 1 }, Danger: { recall: 1 } }, confusion_matrix: [[1, 0, 0], [0, 1, 0], [0, 0, 1]] },
  };
  it("accepts a consistent report", () => expect(checkReport(good).ok).toBe(true));
  it("refuses other files, missing classes and mismatched matrices", () => {
    expect(checkReport({}).ok).toBe(false);
    expect(checkReport(null).ok).toBe(false);
    expect(checkReport({ ...good, classes: [] }).ok).toBe(false);
    expect(checkReport({ ...good, model: { ...good.model, confusion_matrix: [[1, 0], [0, 1]] } }).ok).toBe(false);
    expect(checkReport({ ...good, model: { ...good.model, confusion_matrix: [[-1, 0, 0], [0, 1, 0], [0, 0, 1]] } }).ok).toBe(false);
  });
});
