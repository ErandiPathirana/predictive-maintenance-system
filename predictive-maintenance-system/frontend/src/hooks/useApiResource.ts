import { useCallback, useEffect, useState } from "react";
import { ApiError } from "../api/client";

export type ResourceState<T> =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "success"; data: T };

/** Calls `load` once on mount, and again whenever `reload()` is called.
 *  `load` must be a stable function (defined outside the component). */
export function useApiResource<T>(load: () => Promise<T>) {
  const [state, setState] = useState<ResourceState<T>>({ status: "loading" });

  const run = useCallback(() => {
    let cancelled = false;
    setState({ status: "loading" });
    load()
      .then((data) => !cancelled && setState({ status: "success", data }))
      .catch((err: unknown) => {
        if (cancelled) return;
        const error = err instanceof ApiError ? err : new ApiError("Something unexpected went wrong.", "unknown");
        setState({ status: "error", error });
      });
    return () => {
      cancelled = true;
    };
  }, [load]);

  useEffect(() => run(), [run]);

  return { state, reload: run };
}
