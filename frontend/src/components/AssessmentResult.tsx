import { Accordion, Alert, Badge, Button, Group, List, Stack, Text, Title } from "@mantine/core";
import type { ReactNode } from "react";
import { assessmentToCsv } from "../lib/assessmentExport";
import { fieldLabel } from "../lib/assessmentForm";
import { conditionMeta } from "../lib/condition";
import { formatScore, formatTimestamp } from "../lib/format";
import type { AssessmentResponse, FeatureInfo, RecommendationItem } from "../types/api";
import { ConditionBadge } from "./ConditionBadge";
import { DataTable } from "./DataTable";
import { NotConfirmedStatement } from "./DemoNotice";

const ICON: Record<string, string> = { circle: "●", triangle: "▲", diamond: "◆" };

function Banner({ a }: { a: AssessmentResponse }) {
  const m = conditionMeta(a.predicted_condition);
  const r = a.recommendations;
  return (
    <div className="result-banner" style={{ background: `var(${m.softVar})`, borderColor: `var(${m.colorVar})`, color: "var(--text-primary)" }} data-testid="result-banner" data-condition={a.predicted_condition}>
      <div className="result-banner__state" style={{ color: `var(${m.colorVar})` }}>
        <span aria-hidden="true" className="result-banner__icon">{ICON[m.shape]}</span>
        <div>
          <div className="result-banner__label">Predicted condition</div>
          <div className="result-banner__word">{m.label}</div>
        </div>
      </div>
      <p className="result-banner__headline">{r.headline}</p>
    </div>
  );
}

function ItemCard({ item }: { item: RecommendationItem }) {
  const site = item.source === "site_approved";
  return (
    <li className="rec-item" data-testid="rec-item">
      <div className="rec-item__top">
        <span className="rec-item__no" aria-label={`Priority ${item.priority}`}>{item.priority}</span>
        <div className="rec-item__body">
          <Text fw={600}>{item.action}</Text>
          <Text size="sm" c="dimmed">Why: {item.reason}</Text>
          <Group gap="xs" mt={6}>
            <Badge variant="light" color="gray" radius="sm" tt="none">{item.timing}</Badge>
            <Badge variant="outline" color="gray" radius="sm" tt="none">Who: {item.responsible_role}</Badge>
            <Badge variant={site ? "filled" : "light"} color={site ? "teal" : "yellow"} radius="sm" tt="none">
              {site ? `Site-approved: ${item.source_detail}` : "General guidance"}
            </Badge>
          </Group>
          {item.safety_note && <Text size="sm" mt={6} className="rec-item__safety"><strong>Safety:</strong> {item.safety_note}</Text>}
          {!site && item.requires_confirmation && <Text size="xs" c="dimmed" mt={4}>Requires maintenance-engineer confirmation before it is relied on.</Text>}
        </div>
      </div>
    </li>
  );
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return <div className="fact"><dt>{label}</dt><dd>{children}</dd></div>;
}

/** One assessment: status, what to do, the facts behind it. Used right after "Analyse motor" and when reopening a saved record. */
export function AssessmentResult({ a, features, actions }: { a: AssessmentResponse; features: FeatureInfo[]; actions?: ReactNode }) {
  const r = a.recommendations;
  const scoreRows = Object.entries(a.scores).sort((x, y) => y[1] - x[1]);
  const labelOf = (name: string) => features.find((f) => f.name === name);
  const saveCsv = () => {
    const url = URL.createObjectURL(new Blob([assessmentToCsv(a)], { type: "text/csv" }));
    const el = document.createElement("a");
    el.href = url; el.download = `assessment-${a.assessment_id}.csv`;
    document.body.appendChild(el); el.click(); el.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  return (
    <Stack gap="md" className="result" data-testid="assessment-result">
      {a.duplicate
        ? <Alert color="blue" variant="light" role="status">This submission was already saved as assessment <strong>#{a.assessment_id}</strong>. No second record was created.</Alert>
        : a.saved && <Alert color="green" variant="light" role="status">Saved as assessment <strong>#{a.assessment_id}</strong>. It is now in Assessment history.</Alert>}

      <Banner a={a} />

      {r.urgent && (
        <Alert color="red" variant="filled" title="Contact the responsible maintenance engineer now" role="alert" data-testid="danger-notice" icon={<span aria-hidden="true">◆</span>}>
          <Stack gap={4}>
            <Text size="sm" c="white">This is a decision-support prediction, not a confirmed fault and not a shutdown order. Your site safety procedures always take precedence.</Text>
            <Text size="sm" c="white">Do not open electrical equipment, remove guards or touch moving parts unless you are qualified and authorised. Stop or isolate the motor only through the site&apos;s approved shutdown and lockout/tagout procedure.</Text>
          </Stack>
        </Alert>
      )}

      <section className="panel" aria-labelledby="actions-h">
        <Title order={2} size="h3" id="actions-h">Recommended next steps</Title>
        {r.available && r.items.length > 0
          ? <ol className="rec-list">{r.items.map((i) => <ItemCard key={`${i.priority}-${i.action}`} item={i} />)}</ol>
          : <Alert color="yellow" variant="light" mt="sm">No recommendation is available for the class &quot;{a.predicted_condition}&quot;, because the guidance rules do not cover it. Ask the maintenance engineer to assess the motor.</Alert>}
        <Text size="sm" mt="sm">{r.disclaimer}</Text>
        <Text size="sm" c="dimmed" mt={4}>{r.threshold_note}</Text>
        {r.return_to_service.length > 0 && (
          <Accordion variant="contained" mt="sm">
            <Accordion.Item value="rts">
              <Accordion.Control>Before the motor returns to service: questions to settle</Accordion.Control>
              <Accordion.Panel>
                <List type="ordered" spacing={4} size="sm">{r.return_to_service.map((q) => <List.Item key={q}>{q}</List.Item>)}</List>
                {r.return_to_service_note && <Text size="sm" c="dimmed" mt="xs">{r.return_to_service_note}</Text>}
              </Accordion.Panel>
            </Accordion.Item>
          </Accordion>
        )}
        <Text size="xs" c="dimmed" mt="sm">Guidance rules {r.ruleset_version}{r.site_guidance_version ? `, site guidance ${r.site_guidance_version}` : ""}.{a.recommendations_regenerated ? " These steps were rebuilt from the stored condition because this older record has no stored recommendations." : ""}</Text>
      </section>

      <section className="panel" aria-labelledby="facts-h">
        <Title order={2} size="h3" id="facts-h">Assessment details</Title>
        <dl className="facts">
          <Fact label="Motor">{a.motor_id ?? "Not recorded"}{a.equipment_description ? ` (${a.equipment_description})` : ""}</Fact>
          <Fact label="Readings taken">{formatTimestamp(a.measured_at)}</Fact>
          <Fact label="Model version">{a.model_version}</Fact>
          <Fact label="Recorded by">{a.recorded_by ? `${a.recorded_by} (not verified)` : "Not given"}</Fact>
          <Fact label="Saved">{formatTimestamp(a.created_at)} (UTC)</Fact>
        </dl>
        {(a.demonstration_only || a.provisional_label_provenance) && (
          <Alert color="yellow" variant="light" mt="sm" title="Read with care">
            {a.demonstration_only ? "This model is a demonstration. Do not use the result for operational decisions. " : ""}
            {a.provisional_label_provenance ? "The training labels are provisional, so the result shows agreement with labels of unverified origin." : ""}
          </Alert>
        )}
        <NotConfirmedStatement />
        <Title order={3} size="h4" mt="md">Model scores</Title>
        <Text size="sm" c="dimmed" mb="xs">{a.scores_are_calibrated_probabilities ? "Calibrated probabilities." : "These are raw model scores that add up to 1. They are not calibrated probabilities: a score of 0.8 does not mean an 80% chance."}</Text>
        <DataTable
          caption="Model score for each condition class" rows={scoreRows} rowKey={(r2) => r2[0]}
          columns={[
            { key: "c", header: "Condition", render: (r2) => <ConditionBadge condition={r2[0]} /> },
            { key: "s", header: "Score", numeric: true, render: (r2) => formatScore(r2[1]) },
          ]}
        />
        {a.input_warnings.length > 0 && (
          <Alert color="yellow" variant="light" mt="sm" title="Check these entries">
            <List size="sm">{a.input_warnings.map((w) => <List.Item key={w.feature}>{w.feature}: {w.message}</List.Item>)}</List>
          </Alert>
        )}
        <Title order={3} size="h4" mt="md">Readings used</Title>
        {a.readings
          ? <DataTable caption="Sensor readings used for this assessment" rows={Object.entries(a.readings)} rowKey={(r2) => r2[0]}
              columns={[
                { key: "n", header: "Input", render: (r2) => r2[0] },
                { key: "v", header: "Value", numeric: true, render: (r2) => r2[1] },
                { key: "u", header: "Unit", render: (r2) => { const f = labelOf(r2[0]); return f ? fieldLabel(f).unit : ""; } },
              ]} />
          : <Text size="sm" c="dimmed">{a.readings_stored ? "Readings are not shown for this record." : "The server does not store raw sensor readings by default, so they are not shown for a saved record. They were used for this prediction only."}</Text>}
      </section>

      <Group className="no-print" gap="sm">
        <Button onClick={() => window.print()}>Print or save as PDF</Button>
        <Button variant="default" onClick={saveCsv}>Download steps (CSV)</Button>
        {actions}
      </Group>
    </Stack>
  );
}
