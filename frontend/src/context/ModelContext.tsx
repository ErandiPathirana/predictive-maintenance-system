import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { ApiError, getFeatures, getHealth, getModelInfo } from "../api/client";
import type { BundleInfo, FeatureInfo, HealthResponse } from "../types/api";

interface ModelState {
  loading: boolean;
  health: HealthResponse | null;
  healthError: ApiError | null;
  bundle: BundleInfo | null;
  modelReason: string | null;
  modelError: ApiError | null;
  features: FeatureInfo[];
  reload: () => void;
}

const Ctx = createContext<ModelState | null>(null);
const toApiError = (e: unknown) => (e instanceof ApiError ? e : new ApiError("Something unexpected went wrong.", "unknown"));

/** Loads backend health, the model's description and the feature list once, and shares them with every page. */
export function ModelProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<Omit<ModelState, "reload">>({
    loading: true, health: null, healthError: null, bundle: null, modelReason: null, modelError: null, features: [],
  });
  const [tick, setTick] = useState(0);
  const reload = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    let cancelled = false;
    setState((s) => ({ ...s, loading: true }));
    Promise.allSettled([getHealth(), getModelInfo(), getFeatures()]).then(([h, m, f]) => {
      if (cancelled) return;
      setState({
        loading: false,
        health: h.status === "fulfilled" ? h.value : null,
        healthError: h.status === "rejected" ? toApiError(h.reason) : null,
        bundle: m.status === "fulfilled" ? m.value.bundle : null,
        modelReason: m.status === "fulfilled" ? m.value.reason : null,
        modelError: m.status === "rejected" ? toApiError(m.reason) : null,
        features: f.status === "fulfilled" ? f.value.features : [],
      });
    });
    return () => { cancelled = true; };
  }, [tick]);

  const value = useMemo(() => ({ ...state, reload }), [state, reload]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useModel(): ModelState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useModel must be used inside <ModelProvider>");
  return v;
}
