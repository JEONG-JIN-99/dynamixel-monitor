import { describe, expect, it } from "vitest";
import { appendRecords } from "./analysisHistory";
import type { AnalysisPoint } from "../types/analysis";
const r = (seq: number, elapsedMs: number) => ({
  seq,
  point: { elapsedMs } as AnalysisPoint,
});
describe("analysis history windows", () => {
  it("joins an HTTP prefix and overlapping live samples without duplicates", () => {
    expect(
      appendRecords([r(1, 0), r(2, 100)], [r(2, 100), r(3, 200)], 300).map(
        (r) => r.seq,
      ),
    ).toEqual([1, 2, 3]);
  });
  it("trims by acquisition time, not by count, and includes the boundary", () => {
    expect(
      appendRecords([r(1, 0), r(2, 200)], [r(3, 300200)], 300).map(
        (r) => r.seq,
      ),
    ).toEqual([2, 3]);
  });
  it("keeps the entire experiment without the live buffer capacity limit", () => {
    const values = Array.from({ length: 36001 }, (_, i) => r(i + 1, i * 100));
    expect(appendRecords([], values, 0)).toHaveLength(36001);
    expect(appendRecords([], values, 3600)).toHaveLength(36001);
    expect(appendRecords([], values, 60)).toHaveLength(601);
  });
});
