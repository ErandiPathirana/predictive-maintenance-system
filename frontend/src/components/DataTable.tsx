import type { ReactNode } from "react";

export interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  numeric?: boolean;
}

/** Plain semantic table: caption, header cells with scope, keyboard-scrollable region. */
export function DataTable<T>({ caption, columns, rows, rowKey, label }: {
  caption: string; columns: Column<T>[]; rows: T[]; rowKey: (row: T, index: number) => string | number; label?: string;
}) {
  return (
    <div className="table-wrap" role="region" aria-label={label ?? caption} tabIndex={0}>
      <table className="data-table">
        <caption>{caption}</caption>
        <thead>
          <tr>{columns.map((c) => <th key={c.key} scope="col" className={c.numeric ? "num" : undefined}>{c.header}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={rowKey(r, i)}>
              {columns.map((c) => <td key={c.key} className={c.numeric ? "num" : undefined}>{c.render(r)}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
