import { describe, expect, it } from "vitest";
import features from "../test/fixtures/features.json";
import { assessmentToCsv } from "./assessmentExport";
import { buildRequest, emptyForm, fieldLabel, groupFeatures, hasErrors, isInFuture, outsideTrainingRange, parseReading, timestampProblem, validateForm } from "./assessmentForm";
import assessmentFx from "../test/fixtures/assessment.json";
import type { AssessmentResponse } from "../types/api";

const F = features.features;
const filled = () => {
  const f = emptyForm(F);
  f.motorId = "MOT01"; f.measuredAt = "2025-04-01T07:20";
  F.forEach((x, i) => { f.readings[x.name] = String(10 + i); });
  return f;
};

describe("parseReading", () => {
  it.each(["4.2", "-3", "+7", ".5", "5.", "1e3", " 12 "])("accepts %s", (t) => expect(parseReading(t).ok).toBe(true));
  it.each(["", "  ", "abc", "NaN", "Infinity", "-Infinity", "1,5", "12abc", "0x10", "1e999", "--3", "4.2.1"])("rejects %j", (t) => expect(parseReading(t).ok).toBe(false));
  it("never turns a missing value into zero", () => { const r = parseReading(""); expect(r.ok).toBe(false); });
});

describe("timestamps", () => {
  it("accepts a real local time and rejects impossible ones", () => {
    expect(timestampProblem("2025-04-01T07:20")).toBeUndefined();
    expect(timestampProblem("")).toBeTruthy();
    expect(timestampProblem("yesterday")).toBeTruthy();
    expect(timestampProblem("2025-02-30T10:00")).toBeTruthy();
    expect(timestampProblem("2025-04-01T25:00")).toBeTruthy();
  });
  it("flags the future without blocking", () => {
    expect(isInFuture("2099-01-01T00:00")).toBe(true);
    expect(isInFuture("2000-01-01T00:00")).toBe(false);
    expect(validateForm({ ...filled(), measuredAt: "2099-01-01T00:00" }, F).measuredAt).toBeUndefined();
  });
});

describe("validateForm and buildRequest", () => {
  it("accepts a complete form and builds the exact request", () => {
    const body = buildRequest(filled(), F);
    expect(hasErrors(validateForm(filled(), F))).toBe(false);
    expect(Object.keys(body.readings)).toEqual(F.map((x) => x.name));
    expect(body.readings[F[0].name]).toBe(10);
    expect(body).not.toHaveProperty("equipment_description");
  });
  it("lists every missing or invalid reading and the motor ID", () => {
    const f = filled(); f.readings[F[1].name] = ""; f.readings[F[2].name] = "hot"; f.motorId = "bad id!";
    const e = validateForm(f, F);
    expect(Object.keys(e.readings)).toEqual([F[1].name, F[2].name]);
    expect(e.motorId).toBeTruthy();
  });
  it("refuses control characters and over-long text", () => {
    expect(validateForm({ ...filled(), equipment: "a\nb" }, F).equipment).toBeTruthy();
    expect(validateForm({ ...filled(), recordedBy: "x".repeat(65) }, F).recordedBy).toBeTruthy();
  });
  it("will not build a request from invalid values", () => {
    const f = filled(); f.readings[F[0].name] = "";
    expect(() => buildRequest(f, F)).toThrow();
  });
});

describe("grouping and labels", () => {
  it("groups the 14 inputs by bearing position and keeps operating conditions separate", () => {
    const g = groupFeatures(F);
    expect(g.map((x) => x.title)).toEqual(["Drive end, horizontal", "Drive end, vertical", "Non-drive end, horizontal", "Non-drive end, vertical", "Operating conditions"]);
    expect(g.flatMap((x) => x.features)).toHaveLength(14);
  });
  it("uses the bundle's unit when it has one, and does not reinterpret gE", () => {
    expect(fieldLabel({ ...F[1], unit: "gE" }).unit).toBe("gE");
    expect(fieldLabel(F[1]).label).toBe("gE reading");
    expect(fieldLabel(F[0]).unit).toBe("mm/s");
  });
  it("an unknown feature falls into its own group and keeps its name", () => {
    const g = groupFeatures([...F, { name: "mystery_x", unit: null, description: null, observed_train_min: null, observed_train_max: null }]);
    expect(g[g.length - 1].features.map((x) => x.name)).toContain("mystery_x");
  });
  it("training range is a soft hint only", () => {
    expect(outsideTrainingRange(F[0], "1000")).toMatch(/not an alarm limit/i);
    expect(outsideTrainingRange(F[0], "30")).toBeUndefined();
    expect(outsideTrainingRange(F[0], "abc")).toBeUndefined();
  });
});

describe("assessment CSV", () => {
  it("has one row per step and neutralises formulas", () => {
    const a = JSON.parse(JSON.stringify(assessmentFx)) as AssessmentResponse;
    a.recommendations.items[0].action = "=cmd()";
    const lines = assessmentToCsv(a).trim().split("\r\n");
    expect(lines).toHaveLength(1 + a.recommendations.items.length);
    expect(lines[1]).toContain(`"'=cmd()"`);
  });
});
