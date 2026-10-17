import { conditionMeta } from "../lib/condition";

function Shape({ shape }: { shape: "circle" | "triangle" | "diamond" }) {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true" focusable="false">
      {shape === "circle" && <circle cx="6" cy="6" r="5" fill="currentColor" />}
      {shape === "triangle" && <path d="M6 1 11.5 11 .5 11Z" fill="currentColor" />}
      {shape === "diamond" && <path d="M6 .5 11.5 6 6 11.5.5 6Z" fill="currentColor" />}
    </svg>
  );
}

/** Predicted condition label. Colour + shape + the word, so it never depends on colour alone. "Predicted" keeps it from reading as a fact. */
export function ConditionBadge({ condition, prefix = false }: { condition: string; prefix?: boolean }) {
  const m = conditionMeta(condition);
  return (
    <span className="cond" style={{ background: `var(${m.softVar})`, color: `var(${m.colorVar})` }} data-condition={condition} title={m.meaning}>
      <Shape shape={m.shape} />
      {prefix ? "Predicted " : ""}{m.label}
    </span>
  );
}
