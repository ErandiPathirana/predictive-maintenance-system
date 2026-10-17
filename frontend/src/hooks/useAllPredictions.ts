import { useCallback, useEffect, useState } from "react";
import { ApiError, getPredictions } from "../api/client";
import type { HistoryItem } from "../types/api";

export const PAGE = 500;
export const MAX_PAGES = 10;

export interface AllPredictions {
  loading: boolean;
  error: ApiError | null;
  items: HistoryItem[];
  /** how many stored predictions exist on the server */
  total: number;
  /** true when more exist than were loaded (the newest ones are loaded first) */
  truncated: boolean;
  reload: () => void;
}

/** Loads up to MAX_PAGES x 500 of the newest stored predictions. The backend has no summary endpoint, so the dashboard summarises these. */
export function useAllPredictions(): AllPredictions {
  const [state, setState] = useState<Omit<AllPredictions, "reload">>({ loading: true, error: null, items: [], total: 0, truncated: false });
  const [tick, setTick] = useState(0);
  const reload = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setState((s) => ({ ...s, loading: true, error: null }));
      try {
        const items: HistoryItem[] = [];
        let total = 0;
        for (let page = 0; page < MAX_PAGES; page++) {
          const res = await getPredictions({}, PAGE, page * PAGE);
          total = res.total;
          items.push(...res.items);
          if (items.length >= total || res.items.length === 0) break;
        }
        if (!cancelled) setState({ loading: false, error: null, items, total, truncated: items.length < total });
      } catch (e) {
        if (!cancelled) setState({ loading: false, error: e instanceof ApiError ? e : new ApiError("Something unexpected went wrong.", "unknown"), items: [], total: 0, truncated: false });
      }
    })();
    return () => { cancelled = true; };
  }, [tick]);

  return { ...state, reload };
}
