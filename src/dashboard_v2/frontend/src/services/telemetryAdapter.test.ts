import { describe, expect, it } from "vitest";
import { normalizeSample } from "./telemetryAdapter";
import type { RegisterSample, Sample } from "../types/motor";
const frame: RegisterSample = {
  serverSessionId: "s",
  sourceSessionId: "source",
  runId: "r",
  busId: "b",
  seq: 1,
  id: 1,
  model: "XM430-W210",
  elapsedMs: 0,
  timestamp: 1000,
  receivedAt: 1000,
  registers: {},
};
const r = (raw: number) => ({
  raw,
  receivedAt: 1000,
  status: "received" as const,
});
describe("shared register transport adapter", () => {
  it("derives display fields from received raw readings without requiring duplicate fields", () => {
    const sample = normalizeSample({
      ...frame,
      registers: {
        11: r(4),
        126: r(65535),
        128: r(4294967295),
        132: r(1234),
        140: r(1240),
        144: r(120),
        122: r(1),
        70: r(0),
      },
    });
    expect(sample.position).toBe(1234);
    expect(sample.current).toBeCloseTo(-0.00269);
    expect(sample.velocity).toBeCloseTo(-0.229);
    expect(sample.voltage).toBe(12);
    expect(sample.moving).toBe(true);
    expect(sample.temperature).toBeNull();
    expect(sample.diagnosis).toBeUndefined();
    expect(sample.status).toBeNull();
  });
  it("preserves diagnosis and never substitutes zero for missing/error readings", () => {
    const d = { state: "fault" as const, codes: ["friction"] };
    const sample = normalizeSample({
      ...frame,
      diagnosis: d,
      registers: { 126: { raw: null, status: "error", receivedAt: 1000 } },
    });
    expect(sample.current).toBeNull();
    expect(sample.hwError).toBeNull();
    expect(sample.moving).toBeNull();
    expect(sample.diagnosis).toEqual(d);
  });
  it("keeps existing converted samples compatible", () => {
    const sample = {
      ...frame,
      current: 0.5,
      position: 42,
      registers: undefined,
    } as unknown as Sample;
    expect(normalizeSample(sample)).toBe(sample);
  });
});
