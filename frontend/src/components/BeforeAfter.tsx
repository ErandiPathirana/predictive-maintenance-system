import { Text } from "@mantine/core";
import { compareReadings } from "../lib/maintenance";
import { formatScore } from "../lib/format";
import { ConditionBadge } from "./ConditionBadge";
import { DataTable } from "./DataTable";

export interface Snapshot { label: string; condition: string; readings: Record<string, number> | null | undefined; scores?: Record<string, number> }

/** Before/after view. The condition is always shown; readings only when both assessments have them (the server keeps raw readings only if configured to). */
export function BeforeAfter({ before, after, readableName }: { before: Snapshot; after: Snapshot; readableName?: (n: string) => string }) {
  const rows = compareReadings(before.readings, after.readings);
  const top = (s?: Snapshot["scores"]) => (s ? Math.max(...Object.values(s)) : undefined);
  return (
    <div data-testid="before-after">
      <DataTable caption="Predicted condition before and after the repair" rows={[before, after]} rowKey={(r) => r.label}
        columns={[
          { key: "l", header: "Assessment", render: (r) => r.label },
          { key: "c", header: "Predicted condition", render: (r) => <ConditionBadge condition={r.condition} /> },
          { key: "s", header: "Model score (predicted class)", numeric: true, render: (r) => formatScore(top(r.scores)) },
        ]} />
      {rows ? (
        <DataTable caption="Sensor readings before and after" rows={rows} rowKey={(r) => r.name}
          columns={[
            { key: "n", header: "Input", render: (r) => readableName?.(r.name) ?? r.name },
            { key: "b", header: "Before", numeric: true, render: (r) => r.before },
            { key: "a", header: "After", numeric: true, render: (r) => r.after },
            { key: "d", header: "Change", numeric: true, render: (r) => (r.delta > 0 ? "+" : "") + Number(r.delta.toFixed(4)) },
          ]} />
      ) : (
        <Text size="sm" c="dimmed" mt="xs">Readings are not compared because the server does not store raw sensor readings by default, so one or both sets are unavailable. The conditions above are always compared.</Text>
      )}
      <Text size="sm" mt="xs">A Normal prediction after a repair is not verification. A qualified engineer must verify the motor under the site&apos;s procedures before the case is closed.</Text>
    </div>
  );
}
