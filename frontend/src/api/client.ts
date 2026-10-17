import type { ApiErrorBody, HealthResponse, ModelInfoResponse } from "../types/api";

const DEFAULT_BASE_URL = "http://localhost:8000";

export function getBaseUrl(): string {
  const fromEnv = import.meta.env.VITE_API_BASE_URL as string | undefined;
  return (fromEnv?.trim() || DEFAULT_BASE_URL).replace(/\/+$/, "");
}

/** An error with a plain-English message the UI can show directly. */
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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${getBaseUrl()}${path}`, init);
  } catch {
    // fetch only throws when the server cannot be reached at all.
    throw new ApiError(
      "Cannot reach the prediction server. Check that the backend is running and that you are online.",
      "network_error",
    );
  }

  if (!response.ok) {
    let body: Partial<ApiErrorBody> | undefined;
    try {
      body = (await response.json()) as ApiErrorBody;
    } catch {
      /* the body was not JSON; fall through to the generic message */
    }
    throw new ApiError(
      body?.error?.message ?? `The server returned an unexpected error (${response.status}).`,
      body?.error?.code ?? "http_error",
      response.status,
      body?.error?.details,
    );
  }
  return (await response.json()) as T;
}

export const getHealth = () => request<HealthResponse>("/api/health");
export const getModelInfo = () => request<ModelInfoResponse>("/api/model-info");
