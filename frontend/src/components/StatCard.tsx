import type { ReactNode } from "react";

export function StatCard({ label, value, note }: { label: string; value: ReactNode; note?: ReactNode }) {
  return (
    <div className="panel stat">
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value}</span>
      {note && <span className="stat-label">{note}</span>}
    </div>
  );
}
