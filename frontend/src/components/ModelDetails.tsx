import type { ModelInfoResponse } from "../types/api";

/** Facts about the loaded model, shown only when the model is ready. */
export function ModelDetails({ info }: { info: ModelInfoResponse }) {
  const b = info.bundle;
  if (!info.model_ready || !b) return null;

  const rows: Array<[string, string]> = [
    ["Model", b.model_name],
    ["Version", b.bundle_version],
    ["Sensor inputs", String(b.feature_count)],
    ["Condition classes", b.classes.map((c) => c.name).join(", ")],
    ["Label provenance", b.label_provenance_documented ? "Documented" : "Not documented (provisional)"],
    ["Scores", b.scores_are_calibrated_probabilities ? "Calibrated probabilities" : "Model scores, not calibrated probabilities"],
    ["What it predicts", b.future_failure_prediction_supported ? "Future failures" : "Recorded condition class, not confirmed failure"],
  ];

  return (
    <>
      {b.demonstration_only && (
        <div className="banner" role="note">
          <strong>Demonstration only.</strong> These results must not be used for operational decisions.
        </div>
      )}
      <dl className="facts">
        {rows.map(([term, value]) => (
          <div key={term}>
            <dt>{term}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      <ul className="notes">
        {b.notes.map((n) => (
          <li key={n}>{n}</li>
        ))}
      </ul>
    </>
  );
}
