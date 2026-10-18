import { Alert, List, Text } from "@mantine/core";
import { useModel } from "../context/ModelContext";

/** The one statement that must never be missing next to a prediction. */
export function NotConfirmedStatement() {
  return (
    <Text size="sm" fw={500} data-testid="not-confirmed">
      A predicted condition is a statistical estimate. It is not a confirmed machine failure, and it does not say when anything will fail.
    </Text>
  );
}

/** Honesty banner built from the flags the backend reports about the loaded model. Shows nothing it was not told. */
export function ModelNotice({ compact = false }: { compact?: boolean }) {
  const { bundle, loading, modelError, modelReason } = useModel();
  if (loading) return null;
  if (!bundle) {
    return (
      <Alert color="yellow" variant="light" title={modelError ? "The model could not be checked" : "No model is loaded"} role="status">
        {modelError ? modelError.message : modelReason ?? "The backend has no trained model, so predictions are unavailable."}
      </Alert>
    );
  }
  const items: string[] = [];
  if (bundle.demonstration_only) items.push("Demonstration only. Do not use these results for operational decisions.");
  if (bundle.provisional_label_provenance) items.push("The training labels are provisional. Results show agreement with labels whose origin is not yet verified.");
  if (!bundle.scores_are_calibrated_probabilities) items.push("Scores are model outputs, not calibrated probabilities. A score of 0.8 does not mean an 80% chance.");
  if (!bundle.future_failure_prediction_supported) items.push("The model describes the current condition. It does not predict when a failure will happen.");
  if (items.length === 0) return null;
  const strong = bundle.demonstration_only || bundle.provisional_label_provenance;
  return (
    <Alert color={strong ? "yellow" : "blue"} variant="light" title={compact ? "Read with care" : "How to read these results"} data-testid="model-notice" role="note">
      <List size="sm" spacing={2}>
        {items.map((t) => <List.Item key={t}>{t}</List.Item>)}
      </List>
    </Alert>
  );
}
