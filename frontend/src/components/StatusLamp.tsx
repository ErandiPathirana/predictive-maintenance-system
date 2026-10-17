export type LampTone = "ok" | "warn" | "fault" | "idle";

interface StatusLampProps {
  tone: LampTone;
  title: string;
  /** Short word shown next to the lamp, so state never depends on colour alone. */
  state: string;
  detail?: string;
}

/** One indicator lamp: a coloured dot, a name, a state word and an optional explanation. */
export function StatusLamp({ tone, title, state, detail }: StatusLampProps) {
  return (
    <li className="lamp-row" data-tone={tone}>
      <span className="lamp" aria-hidden="true" />
      <div>
        <p className="lamp-title">
          {title} <span className="lamp-state">{state}</span>
        </p>
        {detail && <p className="lamp-detail">{detail}</p>}
      </div>
    </li>
  );
}
