import { describe, it, expect } from "vitest";
import {
  analysisPoint,
  analysisHistory,
  plotHistory,
  timeSegments,
  stateAt,
} from "./analysis";
import type { MotorFrame } from "../types/analysis";
import type { RegisterReading, MotorMetadata, Sample } from "../types/motor";
const r = (
  raw: number | null,
  receivedAt = 1000,
  status: RegisterReading["status"] = "received",
): RegisterReading => ({ raw, receivedAt, status });
const frame = (
  registers: Record<string, RegisterReading>,
  elapsedMs = 0,
): MotorFrame => ({
  id: 1,
  model: "XM430-W210",
  timestamp: 1000 + elapsedMs,
  elapsedMs,
  registers,
});
describe("transport-independent detailed analysis", () => {
  it("draws from registers alone and computes signed errors in physical units", () => {
    const p = analysisPoint(
      frame({
        11: r(4),
        126: r(65535),
        128: r(4294967295),
        136: r(1),
        132: r(100),
        140: r(90),
        124: r(65535),
        144: r(120),
      }),
    );
    expect(p.current).toBeCloseTo(-0.00269);
    expect(p.pwm).toBeCloseTo(-0.113);
    expect(p.voltage).toBe(12);
    expect(p.positionError).toBe(10);
    expect(p.velocityError).toBeCloseTo(-0.458);
  });
  it("does not fabricate missing readings or fall back after a read failure", () => {
    const p = analysisPoint({
      ...frame({ 126: r(null, 1000, "error"), 132: r(2.5) }),
      current: 3,
    } as unknown as Sample);
    expect(p.current).toBeNull();
    expect(p.position).toBeNull();
    expect(p.temperature).toBeNull();
    expect(p.hardwareError).toBeNull();
    expect(p.diagnosis).toBeUndefined();
  });
  it("requires matched acquisition timestamps and applicable operating modes for errors", () => {
    const raw = {
      11: r(4),
      132: r(30),
      140: r(20, 999),
      128: r(10),
      136: r(5),
    };
    expect(analysisPoint(frame(raw)).positionError).toBeNull();
    expect(
      analysisPoint(frame({ ...raw, 11: r(1) })).velocityError,
    ).toBeCloseTo(1.145);
    expect(
      analysisPoint(frame({ ...raw, 11: r(16) })).velocityError,
    ).toBeNull();
    expect(
      analysisPoint(frame({ ...raw, 11: r(null) })).positionError,
    ).toBeNull();
  });
  it("keeps algorithm verdict separate from hardware flags and large tracking errors", () => {
    const p = analysisPoint(
      frame({ 11: r(4), 70: r(36), 123: r(9), 132: r(99999), 140: r(0) }),
    );
    expect(stateAt(p, "diagnosis").label).toBe("판정 대기");
    expect(stateAt(p, "hardwareError").label).toBe("과열 · 과부하");
    expect(p.followingError).toBe(1);
    expect(p.inPosition).toBe(1);
    p.diagnosis = { state: "normal", codes: [] };
    expect(stateAt(p, "diagnosis").label).toBe("정상");
  });
  it("carries configuration only and refuses metadata from the future", () => {
    const metadata = { registers: { 11: r(4, 5000) } } as Pick<MotorMetadata, "registers">;
    expect(
      analysisPoint(frame({ 132: r(20), 140: r(10) }), metadata).positionError,
    ).toBeNull();
    const result = analysisHistory([
      frame({ 11: r(4), 38: r(1000), 126: r(50) }),
      frame({ 132: r(20, 1100), 140: r(10, 1100) }, 100),
    ]);
    expect(result[1]!.positionError).toBe(10);
    expect(result[1]!.current).toBeNull();
    expect(result[1]!.limits.current?.[0]?.value).toBeCloseTo(2.69);
  });
  it("leaves collection gaps blank and does not stretch a status into the future", () => {
    const points = [0, 100, 5000, 5100].map((t) =>
      analysisPoint(frame({ 64: r(1) }, t)),
    );
    const segments = timeSegments(points, "torque", 100);
    expect(segments).toHaveLength(2);
    expect(segments[0]!.end).toBe(0.25);
    expect(segments[1]!.end).toBe(5.1);
    const plot = plotHistory(points, 100);
    expect(plot).toHaveLength(5);
    expect(plot[2]!.current).toBeNull();
    expect(plot[2]!.elapsedMs).toBe(200);
  });
  it("preserves every sample rather than averaging values within a screen update", () => {
    const points = analysisHistory(
      Array.from({ length: 10 }, (_, i) => frame({ 126: r(i) }, i * 100)),
    );
    expect(points).toHaveLength(10);
    expect(points[9]!.current).toBeCloseTo(0.02421);
  });
  it("does not apply XM430 decoding to unsupported models", () => {
    const p = analysisPoint({ ...frame({ 126: r(100) }), model: "XL430-W250" });
    expect(p.current).toBeNull();
  });
});
