/** The ONLY module that talks to the backend. Pages never call fetch directly. */
import type {
  ApiErrorBody, BatchList, BatchPredictionResponse, CsvValidationReport, FeatureListResponse, HealthResponse,
  HistoryFilters, ModelInfoResponse, PredictionPage,
} from "../types/api";

export const DEFAULT_TIMEOUT_MS = 20_000;
export const UPLOAD_TIMEOUT_MS = 120_000;

/** Base URL comes from VITE_API_BASE_URL. localhost is a fallback for `npm run dev` ONLY:
 *  a production build without the variable reports a configuration error instead of calling localhost. */
export function getBaseUrl(): string {
  const fromEnv = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim();
  if (fromEnv) return fromEnv.replace(/\/+$/, "");
  if (import.meta.env.DEV) return "http://localhost:8000";
  return "";
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly code: string,
    public readonly status?: number,
    public readonly details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// The optional access key lives in memory only (never localStorage). It is NOT a secret once typed into a browser;
// it only keeps casual visitors out. See docs/frontend.md.
let accessKey: string | null = null;
export const setAccessKey = (key: string | null) => { accessKey = key?.trim() || null; };
export const hasAccessKey = () => accessKey !== null;

type Query = Record<string, string | number | undefined>;

function buildUrl(path: string, query?: Query): string {
  const base = getBaseUrl();
  if (!base) {
    throw new ApiError("The backend address is not configured. Set VITE_API_BASE_URL when building the site.", "not_configured");
  }
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(query ?? {})) if (v !== undefined && v !== "") params.set(k, String(v));
  const qs = params.toString();
  return `${base}${path}${qs ? `?${qs}` : ""}`;
}

async function send(path: string, opts: { query?: Query; method?: string; body?: BodyInit; timeoutMs?: number } = {}): Promise<Response> {
  const url = buildUrl(path, opts.query);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), opts.timeoutMs ?? DEFAULT_TIMEOUT_MS);
  let response: Response;
  try {
    response = await fetch(url, {
      method: opts.method ?? "GET",
      body: opts.body,
      headers: accessKey ? { "X-API-Key": accessKey } : undefined,
      signal: controller.signal,
    });
  } catch (err) {
    if ((err as Error)?.name === "AbortError") {
      throw new ApiError("The server took too long to answer. Try again in a moment. On free hosting the first request can take up to a minute.", "timeout");
    }
    throw new ApiError("Cannot reach the prediction server. Check that the backend is running and that you are online.", "network_error");
  } finally {
    clearTimeout(timer);
  }
  if (!response.ok) throw await toApiError(response);
  return response;
}

async function toApiError(response: Response): Promise<ApiError> {
  let body: Partial<ApiErrorBody> | undefined;
  try {
    body = (await response.json()) as ApiErrorBody;
  } catch {
    /* body was not JSON */
  }
  const e = body?.error;
  return new ApiError(
    e?.message ?? `The server returned an unexpected error (${response.status}).`,
    e?.code ?? "http_error",
    response.status,
    e?.details,
  );
}

const json = async <T>(path: string, opts?: Parameters<typeof send>[1]) => (await (await send(path, opts)).json()) as T;

export const getHealth = () => json<HealthResponse>("/api/health");
export const getModelInfo = () => json<ModelInfoResponse>("/api/model-info");
export const getFeatures = () => json<FeatureListResponse>("/api/features");
export const getBatches = () => json<BatchList>("/api/batches");

export function getPredictions(filters: HistoryFilters, limit: number, offset: number) {
  return json<PredictionPage>("/api/predictions", { query: { ...filters, limit, offset } });
}

function csvForm(file: File): FormData {
  const form = new FormData();
  form.append("file", file, file.name);
  return form;
}
export const validateCsv = (file: File) =>
  json<CsvValidationReport>("/api/uploads/validate", { method: "POST", body: csvForm(file), timeoutMs: UPLOAD_TIMEOUT_MS });
export const predictBatch = (file: File) =>
  json<BatchPredictionResponse>("/api/predict/batch", { method: "POST", body: csvForm(file), timeoutMs: UPLOAD_TIMEOUT_MS });

export interface DownloadedFile { blob: Blob; filename: string; truncated: boolean; totalMatching: number | null; rowsExported: number | null }

async function download(path: string, query?: Query): Promise<DownloadedFile> {
  const r = await send(path, { query, timeoutMs: UPLOAD_TIMEOUT_MS });
  const disposition = r.headers.get("content-disposition") ?? "";
  const num = (h: string) => { const v = r.headers.get(h); return v === null ? null : Number(v); };
  return {
    blob: await r.blob(),
    filename: /filename="?([^";]+)"?/.exec(disposition)?.[1] ?? "download.csv",
    truncated: r.headers.get("x-export-truncated") === "true",
    totalMatching: num("x-total-matching"),
    rowsExported: num("x-rows-exported"),
  };
}
export const downloadTemplate = () => download("/api/template.csv");
export const downloadReport = (filters: HistoryFilters) => download("/api/reports/predictions.csv", filters as Query);

/** Saves a downloaded file through the browser. */
export function saveFile(file: DownloadedFile): void {
  const url = URL.createObjectURL(file.blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = file.filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** The saved research evaluation report is a static file served with the site (not a backend endpoint). */
export async function getEvaluationReport(): Promise<unknown | null> {
  let r: Response;
  try {
    r = await fetch(`${import.meta.env.BASE_URL}evaluation_report.json`, { cache: "no-store" });
  } catch {
    throw new ApiError("Could not load the saved evaluation report.", "network_error");
  }
  const type = r.headers.get("content-type") ?? "";
  // A static host may answer a missing file with index.html (status 200): treat anything that is not JSON as "no report".
  if (r.status === 404 || !type.includes("json")) return null;
  if (!r.ok) throw new ApiError(`Could not load the saved evaluation report (${r.status}).`, "http_error", r.status);
  try {
    return await r.json();
  } catch {
    throw new ApiError("The saved evaluation report is not valid JSON.", "bad_report");
  }
}
