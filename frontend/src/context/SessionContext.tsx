import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import type { BatchPredictionResponse, CsvValidationReport } from "../types/api";

/** The file the user chose, kept in MEMORY ONLY (never localStorage), so confidential sensor data is gone on refresh or close. */
export interface UploadedDataset {
  fileName: string;
  columns: string[];
  rows: Record<string, string>[];
  loadedAt: Date;
}

interface SessionState {
  dataset: UploadedDataset | null;
  file: File | null;
  validation: CsvValidationReport | null;
  analysis: BatchPredictionResponse | null;
  setDataset: (d: UploadedDataset | null, file: File | null) => void;
  setValidation: (v: CsvValidationReport | null) => void;
  setAnalysis: (a: BatchPredictionResponse | null) => void;
  clear: () => void;
}

const Ctx = createContext<SessionState | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [dataset, setDatasetState] = useState<UploadedDataset | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [validation, setValidation] = useState<CsvValidationReport | null>(null);
  const [analysis, setAnalysis] = useState<BatchPredictionResponse | null>(null);

  const setDataset = useCallback((d: UploadedDataset | null, f: File | null) => {
    setDatasetState(d); setFile(f); setValidation(null); setAnalysis(null); // a new file invalidates old results
  }, []);
  const clear = useCallback(() => setDataset(null, null), [setDataset]);

  const value = useMemo(
    () => ({ dataset, file, validation, analysis, setDataset, setValidation, setAnalysis, clear }),
    [dataset, file, validation, analysis, setDataset, clear],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useSession(): SessionState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useSession must be used inside <SessionProvider>");
  return v;
}
