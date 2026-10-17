import { List, Text, Title } from "@mantine/core";
import { useEffect, useState } from "react";
import { getEvaluationReport } from "../api/client";
import { DataTable } from "../components/DataTable";
import { PageHeader } from "../components/PageHeader";
import { EmptyState, LoadingBlock } from "../components/StateViews";
import { useModel } from "../context/ModelContext";
import { conditionMeta } from "../lib/condition";
import { checkReport } from "../lib/evaluation";
import { formatMetric } from "../lib/format";

const Section = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <section className="panel" style={{ marginBottom: 16 }} aria-label={title}><Title order={2} size="h4" mb="xs">{title}</Title>{children}</section>
);

export default function ResearchPage() {
  const { bundle, features, loading, modelReason, modelError } = useModel();
  const [origin, setOrigin] = useState<string>("loading");
  useEffect(() => {
    getEvaluationReport().then((raw) => { if (raw === null) return setOrigin("none"); const c = checkReport(raw); setOrigin(c.ok ? c.report.data_origin : "invalid"); }).catch(() => setOrigin("error"));
  }, []);

  return (
    <>
      <PageHeader title="Research information" intro="What this prototype is for, what it uses, and where its limits are." />
      <Section title="Purpose">
        <Text>This website is the interface of a research artefact: <em>a machine learning approach to proactive machine failure prediction for modern manufacturing systems</em>.
          It uses vibration, gE and temperature readings from motor bearings, together with speed and load, to estimate which condition class a record resembles, so maintenance staff can look at the motors that matter first.</Text>
        <Text mt="xs">It is decision support for a research study. It is not a safety system and does not replace inspection by a qualified person.</Text>
      </Section>

      <Section title="Target classes">
        {loading ? <LoadingBlock /> : !bundle ? (
          <EmptyState title="Model details unavailable">{modelError?.message ?? modelReason ?? "The backend has no model loaded."}</EmptyState>
        ) : (
          <DataTable caption="Condition classes the model can predict" rows={bundle.classes} rowKey={(c) => c.id}
            columns={[{ key: "n", header: "Class", render: (c) => c.name }, { key: "m", header: "What a prediction means", render: (c) => conditionMeta(c.name).meaning }]} />
        )}
      </Section>

      <Section title="Model in use">
        {bundle ? (
          <dl style={{ display: "grid", gridTemplateColumns: "max-content 1fr", gap: "4px 16px", margin: 0 }}>
            <dt>Name</dt><dd style={{ margin: 0 }}>{bundle.model_name}</dd>
            <dt>Version</dt><dd style={{ margin: 0 }}>{bundle.bundle_version}</dd>
            <dt>Task</dt><dd style={{ margin: 0 }}>{bundle.task ?? "Not recorded"}</dd>
            <dt>Created</dt><dd style={{ margin: 0 }}>{bundle.created_utc ?? "Not recorded"}</dd>
            <dt>Input features</dt><dd style={{ margin: 0 }}>{bundle.feature_count}</dd>
            <dt>Demonstration only</dt><dd style={{ margin: 0 }}>{bundle.demonstration_only ? "Yes" : "No"}</dd>
            <dt>Training labels provisional</dt><dd style={{ margin: 0 }}>{bundle.provisional_label_provenance ? "Yes, origin not yet verified" : "No"}</dd>
            <dt>Scores calibrated</dt><dd style={{ margin: 0 }}>{bundle.scores_are_calibrated_probabilities ? "Yes" : "No, raw model outputs"}</dd>
            <dt>Future-failure prediction</dt><dd style={{ margin: 0 }}>{bundle.future_failure_prediction_supported ? "Supported" : "Not supported"}</dd>
            {bundle.reported_test_metrics && <><dt>Notebook test macro F1</dt><dd style={{ margin: 0 }}>{formatMetric(bundle.reported_test_metrics.macro_f1)} (see Model evaluation)</dd></>}
          </dl>
        ) : <Text c="dimmed">Not available until the backend has a model loaded.</Text>}
      </Section>

      <Section title="Features used">
        {features.length === 0 ? <Text c="dimmed">The feature list appears when the backend is reachable.</Text> : (
          <DataTable caption="The model's 14 inputs, with the range seen in the training data"
            rows={features} rowKey={(f) => f.name}
            columns={[
              { key: "n", header: "Column", render: (f) => <code>{f.name}</code> },
              { key: "d", header: "Meaning", render: (f) => f.description ?? "" },
              { key: "u", header: "Unit", render: (f) => f.unit ?? "" },
              { key: "lo", header: "Training min", numeric: true, render: (f) => formatMetric(f.observed_train_min, 2) },
              { key: "hi", header: "Training max", numeric: true, render: (f) => formatMetric(f.observed_train_max, 2) },
            ]} />
        )}
      </Section>

      <Section title="Validated results versus synthetic demonstrations">
        <Text>Numbers computed on real, measured plant data with verified labels are the only ones that say anything about real-world performance. Results from generated (synthetic) data only show that the software works end to end.</Text>
        <List mt="xs" spacing={4}>
          <List.Item>Evaluation report data origin: <strong>{origin === "loading" ? "checking…" : origin === "none" ? "no report saved" : origin === "invalid" || origin === "error" ? "report unreadable" : origin}</strong>.</List.Item>
          <List.Item>Loaded model: <strong>{!bundle ? "not available" : bundle.demonstration_only ? "flagged as demonstration only" : "not flagged as demonstration"}</strong>; labels {!bundle ? "unknown" : bundle.provisional_label_provenance ? "provisional" : "not flagged as provisional"}.</List.Item>
        </List>
      </Section>

      <Section title="Limitations">
        <List spacing={4}>
          <List.Item>A prediction is the model's estimate of a condition class. It is not a confirmed failure and gives no time-to-failure.</List.Item>
          <List.Item>The model can only be as good as the Alert and Danger labels it learned from. Where those labels came from must be documented before results are used to support decisions.</List.Item>
          <List.Item>Scores are not calibrated probabilities.</List.Item>
          <List.Item>The model has only seen the motors and operating conditions in its training data. Inputs outside the training range are flagged as warnings, but a motor of a different type may behave differently.</List.Item>
          <List.Item>The definitions of the gE measure and of the vibration velocity type (RMS, peak) are not stated in the source data.</List.Item>
          <List.Item>The evaluation covers held-out motors from one dataset. It does not show how the model performs at another site.</List.Item>
        </List>
      </Section>
    </>
  );
}
