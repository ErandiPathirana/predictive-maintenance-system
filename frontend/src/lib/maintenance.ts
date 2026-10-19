import type { MaintenanceStatus } from "../types/api";

export const STATUS_LABEL: Record<MaintenanceStatus, string> = {
  pending_inspection: "Pending Inspection",
  maintenance_in_progress: "Maintenance In Progress",
  repair_completed_verification_required: "Repair Completed: Verification Required",
  verified_closed: "Verified / Closed",
};
export const STATUS_ORDER: MaintenanceStatus[] = ["pending_inspection", "maintenance_in_progress", "repair_completed_verification_required", "verified_closed"];

export const assessmentRef = (id: number) => `PM-${String(id).padStart(6, "0")}`;
export const isFollowUpCondition = (c: string) => c === "Alert" || c === "Danger";

/** Same shape the server accepts (see backend report_email.valid_email). The server checks again; this only gives quick feedback. */
export const EMAIL_PATTERN = /^[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9-]{1,63}(\.[A-Za-z0-9-]{1,63})+$/;
export const isValidEmail = (v: string) => v.length <= 254 && EMAIL_PATTERN.test(v);

export interface ReadingChange { name: string; before: number; after: number; delta: number }

/** Compares only the inputs present in BOTH sets. Returns null when either side has no readings, so nothing is invented. */
export function compareReadings(before: Record<string, number> | null | undefined, after: Record<string, number> | null | undefined): ReadingChange[] | null {
  if (!before || !after) return null;
  const rows = Object.keys(before).filter((k) => k in after).map((name) => ({ name, before: before[name], after: after[name], delta: after[name] - before[name] }));
  return rows.length ? rows : null;
}
