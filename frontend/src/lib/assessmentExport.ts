import type { AssessmentResponse } from "../types/api";
import { formatTimestamp, safeCell } from "./format";

/** One row per recommendation, so a spreadsheet user can filter by timing or role. Text cells are protected against formula injection. */
export function assessmentToCsv(a: AssessmentResponse): string {
  const head = ["assessment_id", "motor_id", "measured_at", "predicted_condition", "model_version", "ruleset_version", "priority", "timing", "responsible_role", "action", "reason", "safety_note", "source"];
  const rows = a.recommendations.items.length
    ? a.recommendations.items.map((i) => [a.assessment_id, a.motor_id, formatTimestamp(a.measured_at), a.predicted_condition, a.model_version, a.recommendations.ruleset_version, i.priority, i.timing, i.responsible_role, i.action, i.reason, i.safety_note ?? "", i.source === "site_approved" ? `Site-approved: ${i.source_detail}` : "General guidance (needs engineer confirmation)"])
    : [[a.assessment_id, a.motor_id, formatTimestamp(a.measured_at), a.predicted_condition, a.model_version, a.recommendations.ruleset_version, "", "", "", a.recommendations.headline, "", "", ""]];
  const q = (v: unknown) => `"${safeCell(v).replace(/"/g, '""')}"`;
  return [head.join(","), ...rows.map((r) => r.map(q).join(","))].join("\r\n") + "\r\n";
}
