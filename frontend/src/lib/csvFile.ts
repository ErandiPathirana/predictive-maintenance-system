import Papa from "papaparse";

/** Mirrors the backend defaults for a fast, friendly pre-check. The BACKEND is the authority and may use other limits. */
export const CLIENT_MAX_BYTES = 2_000_000;
export const CLIENT_MAX_ROWS = 5000;
export const ID_COLUMNS = ["record_id", "motor_id"] as const;
export const OPTIONAL_COLUMNS = ["measured_at"] as const;

export interface ParsedCsv {
  columns: string[];
  rows: Record<string, string>[];
  parseErrors: string[];
}

export function quickFileCheck(file: File): string | null {
  if (!/\.csv$/i.test(file.name)) return "Please choose a .csv file.";
  if (file.size === 0) return "The file is empty.";
  if (file.size > CLIENT_MAX_BYTES) return `The file is ${(file.size / 1e6).toFixed(1)} MB. The default limit is ${(CLIENT_MAX_BYTES / 1e6).toFixed(0)} MB.`;
  return null;
}

/** Parses in the browser only. Nothing is sent anywhere by this function. */
export function parseCsvFile(file: File): Promise<ParsedCsv> {
  return new Promise((resolve, reject) => {
    Papa.parse<Record<string, string>>(file, {
      header: true,
      skipEmptyLines: "greedy",
      transformHeader: (h) => h.replace(/^﻿/, "").trim(),
      complete: (res) =>
        resolve({
          columns: res.meta.fields ?? [],
          rows: res.data,
          parseErrors: res.errors.slice(0, 5).map((e) => `Row ${e.row !== undefined ? e.row + 2 : "?"}: ${e.message}`),
        }),
      error: (err: Error) => reject(err),
    });
  });
}

export function missingColumns(columns: string[], features: string[]): string[] {
  const have = new Set(columns);
  return [...ID_COLUMNS, ...features].filter((c) => !have.has(c));
}

export function toCsvText(rows: Record<string, unknown>[], columns: string[]): string {
  return Papa.unparse({ fields: columns, data: rows.map((r) => columns.map((c) => r[c] ?? "")) }, { newline: "\r\n" });
}
