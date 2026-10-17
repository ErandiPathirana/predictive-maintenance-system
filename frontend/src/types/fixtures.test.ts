// These JSON files are REAL responses captured from the running backend (backend/scripts/export_api_fixtures.py).
// Assigning them to the interfaces below makes `npm run typecheck` fail if the backend schema and the frontend types drift apart.
import type { ApiErrorBody, BatchList, BatchPredictionResponse, CsvValidationReport, FeatureListResponse, HealthResponse, ModelInfoResponse, PredictionPage, PredictionResult } from "./api";
import batch from "../test/fixtures/batch_response.json";
import batches from "../test/fixtures/batches.json";
import errorInvalid from "../test/fixtures/error_invalid_request.json";
import errorNotFound from "../test/fixtures/error_not_found.json";
import features from "../test/fixtures/features.json";
import health from "../test/fixtures/health.json";
import modelInfo from "../test/fixtures/model_info.json";
import page from "../test/fixtures/predictions_page.json";
import single from "../test/fixtures/predict_single.json";
import validateBad from "../test/fixtures/validate_bad.json";
import validateOk from "../test/fixtures/validate_ok.json";

describe("frontend types match real backend responses", () => {
  it("compiles and has the key fields", () => {
    const h: HealthResponse = health;
    const m: ModelInfoResponse = modelInfo;
    const f: FeatureListResponse = features;
    const b: BatchPredictionResponse = batch;
    const s: PredictionResult = single;
    const p: PredictionPage = page;
    const bl: BatchList = batches;
    const vo: CsvValidationReport = validateOk;
    const vb: CsvValidationReport = validateBad;
    const e1: ApiErrorBody = errorInvalid;
    const e2: ApiErrorBody = errorNotFound;
    expect(h.model_ready).toBe(true);
    expect(m.bundle?.classes.map((c) => c.name)).toEqual(["Normal", "Alert", "Danger"]);
    expect(f.features).toHaveLength(14);
    expect(b.results).toHaveLength(b.record_count);
    expect(s.scores_are_calibrated_probabilities).toBe(false);
    expect(p.items.length).toBeGreaterThan(0);
    expect(bl.items.length).toBeGreaterThan(0);
    expect(vo.valid).toBe(true);
    expect(vb.valid).toBe(false);
    expect(e1.error.code).toBeTruthy();
    expect(e2.error.code).toBeTruthy();
  });
});
