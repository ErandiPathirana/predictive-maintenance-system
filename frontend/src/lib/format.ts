/** The backend returns timestamps WITHOUT a time zone, exactly as recorded. We show them as recorded and never shift them. */
export function formatTimestamp(value: string | null | undefined): string {
  if (!value) return "Not recorded";
  const m = /^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})(?::\d{2})?/.exec(value);
  return m ? `${m[1]} ${m[2]}` : value;
}

/** Milliseconds for ordering only (time zone is irrelevant when every value is compared the same way). NaN when unparseable. */
export function sortableTime(value: string | null | undefined): number {
  if (!value) return Number.NaN;
  return Date.parse(value.includes("T") ? value : value.replace(" ", "T"));
}

export const formatScore = (v: number | undefined): string => (v === undefined || Number.isNaN(v) ? "n/a" : v.toFixed(3));
export const formatMetric = (v: number | null | undefined, digits = 3): string => (v === null || v === undefined || Number.isNaN(v) ? "n/a" : v.toFixed(digits));
export const formatInt = (v: number): string => v.toLocaleString("en-GB");

/** Guards against spreadsheet formula injection when WE write CSV cells (history export is made by the backend). */
export function safeCell(v: unknown): string {
  const s = v === null || v === undefined ? "" : String(v);
  return /^[=+\-@\t\r]/.test(s) ? `'${s}` : s;
}
