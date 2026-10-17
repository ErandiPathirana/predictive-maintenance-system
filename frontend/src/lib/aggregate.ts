import type { HistoryItem } from "../types/api";
import { CONDITION_ORDER } from "./condition";
import { sortableTime } from "./format";

export const NO_MOTOR = "(no motor ID)";

export interface MotorLatest {
  motorId: string;
  item: HistoryItem;
  /** "measured_at" = ordered by the reading's own timestamp. "stored_at" = the motor has NO timestamped records, so the time
   *  the prediction was stored is used instead, and the page says so. */
  basis: "measured_at" | "stored_at";
  recordCount: number;
}

const motorOf = (i: HistoryItem) => i.motor_id ?? NO_MOTOR;

export function latestPerMotor(items: HistoryItem[]): MotorLatest[] {
  const groups = new Map<string, HistoryItem[]>();
  for (const it of items) {
    const k = motorOf(it);
    (groups.get(k) ?? groups.set(k, []).get(k)!).push(it);
  }
  const out: MotorLatest[] = [];
  for (const [motorId, list] of groups) {
    const timed = list.filter((i) => !Number.isNaN(sortableTime(i.measured_at)));
    const pool = timed.length ? timed : list;
    const key = (i: HistoryItem) => (timed.length ? sortableTime(i.measured_at) : sortableTime(i.created_at));
    const best = pool.reduce((a, b) => (key(b) > key(a) || (key(b) === key(a) && b.id > a.id) ? b : a));
    out.push({ motorId, item: best, basis: timed.length ? "measured_at" : "stored_at", recordCount: list.length });
  }
  return out.sort((a, b) => a.motorId.localeCompare(b.motorId, undefined, { numeric: true }));
}

export function countConditions(conditions: string[]): Record<string, number> {
  const counts: Record<string, number> = Object.fromEntries(CONDITION_ORDER.map((c) => [c, 0]));
  for (const c of conditions) counts[c] = (counts[c] ?? 0) + 1;
  return counts;
}

export const recentActivity = (items: HistoryItem[], n: number): HistoryItem[] =>
  [...items].sort((a, b) => sortableTime(b.created_at) - sortableTime(a.created_at) || b.id - a.id).slice(0, n);

/** Highest score = the class the model chose. Returns the score of the predicted class, if present. */
export const topScore = (i: { scores: Record<string, number>; predicted_condition: string }): number | undefined => i.scores[i.predicted_condition];
