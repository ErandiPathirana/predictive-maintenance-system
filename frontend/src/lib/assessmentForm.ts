/** Pure form logic for the New Motor Assessment page: grouping, strict number parsing, validation and the request body.
 *  Nothing here talks to the network, so it can be tested on its own. */
import type { AssessmentRequest, FeatureInfo } from "../types/api";

export const MOTOR_ID_PATTERN = /^[A-Za-z0-9._-]{1,64}$/;
// eslint-disable-next-line no-control-regex
const CONTROL_CHARS = /[\u0000-\u001f\u007f]/;
export const MAX_DESCRIPTION = 120;
export const MAX_RECORDED_BY = 64;

/** Strict decimal: optional sign, digits with an optional dot, optional exponent. Rejects "", "abc", "NaN", "Infinity", "1,5", "12abc", "0x10". */
const DECIMAL = /^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$/;

export type ParsedNumber = { ok: true; value: number } | { ok: false; problem: string };

export function parseReading(text: string): ParsedNumber {
  const t = text.trim();
  if (t === "") return { ok: false, problem: "Enter a value. Missing readings are never replaced with zero." };
  if (t.includes(",")) return { ok: false, problem: "Use a dot for decimals, for example 2.5." };
  if (!DECIMAL.test(t)) return { ok: false, problem: "Enter a number such as 4.2 (digits only, no units or letters)." };
  const n = Number(t);
  if (!Number.isFinite(n)) return { ok: false, problem: "That number is too large." };
  return { ok: true, value: n };
}

/** Sensor inputs are grouped by the prefix of the feature name. Unknown prefixes land in "Other inputs", so another model bundle still works. */
export interface FieldGroup { id: string; title: string; features: FeatureInfo[] }

const GROUPS: { id: string; title: string; prefix: string }[] = [
  { id: "de_h", title: "Drive end, horizontal", prefix: "de_h_" },
  { id: "de_v", title: "Drive end, vertical", prefix: "de_v_" },
  { id: "nde_h", title: "Non-drive end, horizontal", prefix: "nde_h_" },
  { id: "nde_v", title: "Non-drive end, vertical", prefix: "nde_v_" },
];

export function groupFeatures(features: FeatureInfo[]): FieldGroup[] {
  const out: FieldGroup[] = GROUPS.map((g) => ({ id: g.id, title: g.title, features: features.filter((f) => f.name.startsWith(g.prefix)) }));
  const known = new Set(out.flatMap((g) => g.features.map((f) => f.name)));
  const other = features.filter((f) => !known.has(f.name));
  if (other.length) out.push({ id: "other", title: "Operating conditions", features: other });
  return out.filter((g) => g.features.length > 0);
}

const KINDS: [RegExp, string, string][] = [
  [/velocity/, "Vibration velocity", "mm/s"],
  [/_ge$/, "gE reading", ""],
  [/temp/, "Temperature", "°C"],
  [/rotational_speed/, "Rotational speed", "rpm"],
  [/load/, "Load", "%"],
];

/** Label and unit for one field. The unit from the model bundle wins; the name-based unit is only a fallback. gE is not reinterpreted. */
export function fieldLabel(f: FeatureInfo): { label: string; unit: string } {
  const k = KINDS.find(([re]) => re.test(f.name));
  const unit = f.unit && f.unit !== "u" ? f.unit : (k?.[2] ?? f.unit ?? "");
  return { label: k?.[1] ?? f.name, unit };
}

export interface FormValues {
  motorId: string;
  equipment: string;
  measuredAt: string; // datetime-local value "YYYY-MM-DDTHH:mm"
  recordedBy: string;
  readings: Record<string, string>;
}

export const emptyForm = (features: FeatureInfo[]): FormValues => ({
  motorId: "", equipment: "", measuredAt: "", recordedBy: "", readings: Object.fromEntries(features.map((f) => [f.name, ""])),
});

export interface FormErrors { motorId?: string; equipment?: string; measuredAt?: string; recordedBy?: string; readings: Record<string, string> }

export const hasErrors = (e: FormErrors) => !!(e.motorId || e.equipment || e.measuredAt || e.recordedBy || Object.keys(e.readings).length);

const TIMESTAMP = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?$/;

export function timestampProblem(value: string): string | undefined {
  if (!value.trim()) return "Enter the date and time the readings were taken.";
  const m = TIMESTAMP.exec(value.trim());
  if (!m) return "Enter a valid date and time.";
  const [y, mo, d, h, mi] = m.slice(1, 6).map(Number);
  const dt = new Date(y, mo - 1, d, h, mi);
  if (dt.getFullYear() !== y || dt.getMonth() !== mo - 1 || dt.getDate() !== d || h > 23 || mi > 59) return "That date or time does not exist.";
  return undefined;
}

/** True when the entered time is later than now. This is a warning, not an error: clocks can differ. */
export function isInFuture(value: string, now: Date = new Date()): boolean {
  if (timestampProblem(value)) return false;
  return new Date(value).getTime() > now.getTime() + 5 * 60_000;
}

export function validateForm(v: FormValues, features: FeatureInfo[]): FormErrors {
  const e: FormErrors = { readings: {} };
  const id = v.motorId.trim();
  if (!id) e.motorId = "Choose a motor or type its ID.";
  else if (!MOTOR_ID_PATTERN.test(id)) e.motorId = "Use only letters, digits, dot, dash and underscore (up to 64 characters), with no spaces.";
  e.measuredAt = timestampProblem(v.measuredAt);
  if (v.equipment.length > MAX_DESCRIPTION) e.equipment = `Keep this under ${MAX_DESCRIPTION} characters.`;
  else if (CONTROL_CHARS.test(v.equipment)) e.equipment = "Remove line breaks and control characters.";
  if (v.recordedBy.length > MAX_RECORDED_BY) e.recordedBy = `Keep this under ${MAX_RECORDED_BY} characters.`;
  else if (CONTROL_CHARS.test(v.recordedBy)) e.recordedBy = "Remove line breaks and control characters.";
  for (const f of features) {
    const r = parseReading(v.readings[f.name] ?? "");
    if (!r.ok) e.readings[f.name] = r.problem;
  }
  if (!e.motorId) delete e.motorId;
  if (!e.measuredAt) delete e.measuredAt;
  if (!e.equipment) delete e.equipment;
  if (!e.recordedBy) delete e.recordedBy;
  return e;
}

/** Builds the request body. Call only after validateForm reported no errors. */
export function buildRequest(v: FormValues, features: FeatureInfo[]): AssessmentRequest {
  const readings: Record<string, number> = {};
  for (const f of features) {
    const r = parseReading(v.readings[f.name] ?? "");
    if (!r.ok) throw new Error(`Cannot build the request: ${f.name} is invalid.`);
    readings[f.name] = r.value;
  }
  const body: AssessmentRequest = { motor_id: v.motorId.trim(), measured_at: v.measuredAt.trim(), readings };
  if (v.equipment.trim()) body.equipment_description = v.equipment.trim();
  if (v.recordedBy.trim()) body.recorded_by = v.recordedBy.trim();
  return body;
}

/** A soft, non-blocking hint when a valid number lies outside the range seen in the training data. This is NOT an engineering limit. */
export function outsideTrainingRange(f: FeatureInfo, text: string): string | undefined {
  const r = parseReading(text);
  if (!r.ok || f.observed_train_min === null || f.observed_train_max === null) return undefined;
  if (r.value < f.observed_train_min || r.value > f.observed_train_max) {
    return `Outside the range seen in training data (${fmt(f.observed_train_min)} to ${fmt(f.observed_train_max)}). This is not an alarm limit. Check the value was typed correctly. You can still analyse it.`;
  }
  return undefined;
}

const fmt = (n: number) => (Math.abs(n) >= 100 ? n.toFixed(0) : n.toFixed(2));

export function newIdempotencyKey(): string {
  const c = globalThis.crypto as Crypto | undefined;
  if (c?.randomUUID) return `form-${c.randomUUID()}`;
  return `form-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}

/** Local "now" in the datetime-local format. */
export function nowLocalInput(d: Date = new Date()): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}
