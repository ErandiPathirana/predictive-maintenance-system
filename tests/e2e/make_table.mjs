// Builds a Markdown results table from results-*.json
import { readFileSync, readdirSync, writeFileSync } from "node:fs";
const rows = [];
for (const f of readdirSync(".").filter((f) => /^results-.*\.json$/.test(f)).sort()) for (const r of JSON.parse(readFileSync(f, "utf8"))) rows.push({ ...r, file: f });
const esc = (s) => String(s ?? "").replace(/\|/g, "\\|").replace(/\n/g, " ");
let md = "| ID | Scenario | Viewport | Test | Result | Note |\n|---|---|---|---|---|---|\n";
for (const r of rows) md += `| ${r.id} | ${esc(r.file.replace(/^results-|\.json$/g, ""))} | ${r.viewport} | ${esc(r.title)} | **${r.status}** | ${esc(r.note).slice(0, 160)} |\n`;
const c = (s) => rows.filter((r) => r.status === s).length;
md += `\nTotal ${rows.length}: ${c("PASS")} PASS, ${c("FAIL")} FAIL, ${c("N/A")} N/A\n`;
writeFileSync("results-table.md", md); console.log(`Total ${rows.length}: ${c("PASS")} PASS, ${c("FAIL")} FAIL, ${c("N/A")} N/A`);
