import type { ModelInfoResponse } from "../types/api";

/** Facts about the loaded model, shown only when the model is ready. */
export function ModelDetails({ info }: { info: ModelInfoResponse }) {
  const m = info.metadata;
  if (!info.model_ready || !m) return null;

  const rows: Array<[string, string]> = [
    ["Model", m.model_name],
    ["Version", m.model_version],
    ["Sensor inputs", String(info.feature_count ?? "unknown")],
    ["Failure class", String(m.positive_class)],
    [
      "Decision threshold",
      m.decision_threshold != null ? String(m.decision_threshold) : "Not set (the model's own decision is used)",
    ],
  ];
  if (m.trained_at) rows.push(["Trained", new Date(m.trained_at).toLocaleDateString()]);

  return (
    <dl className="facts">
      {rows.map(([term, value]) => (
        <div key={term}>
          <dt>{term}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}
