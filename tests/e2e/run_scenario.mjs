// Usage: node run.mjs <scenario>   (backend for that scenario must already be running on :8000, frontend preview on :5173)
import { launch, closeBrowser, writeResults, results } from "./lib.mjs";
import { conditionTests, dangerExtras, resultAxe } from "./suite_assess.mjs";
import { responsiveTests, accessibilityTests, keyboardTests } from "./suite_ux.mjs";
import { noModelTests, outageTests, slowTests } from "./suite_resilience.mjs";
import { uploadTests, historyTests, monitoringTests } from "./suite_data.mjs";
const scenario = process.argv[2];
await launch();
if (["Normal", "Alert", "Danger"].includes(scenario)) { await conditionTests(scenario); await resultAxe(scenario); }
if (scenario === "Danger") { await dangerExtras(); await uploadTests(); await historyTests(); await monitoringTests(); await keyboardTests(); await accessibilityTests(); await responsiveTests(); }
if (scenario === "NoModel") await noModelTests();
if (scenario === "Outage") await outageTests();
if (scenario === "Slow") await slowTests();
await closeBrowser();
writeResults(`results-${scenario}.json`);
const bad = results.filter((r) => r.status !== "PASS");
console.log(`\n${results.length - bad.length}/${results.length} passed`);
process.exit(bad.length ? 1 : 0);
