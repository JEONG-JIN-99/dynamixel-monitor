import { describe, it, expect } from "vitest";
import { shaftAngle, shaftDegrees } from "./shaftRotation";
describe("shaft angle", () => {
  it("keeps three complete turns instead of losing them to modulo", () => {
    expect(shaftAngle(100 + 3 * 4096, 100)).toBeCloseTo(6 * Math.PI);
    expect(shaftDegrees(shaftAngle(100 + 3 * 4096, 100))).toBeCloseTo(0);
  });
  it("returns to origin and respects negative rotation", () => {
    expect(shaftDegrees(shaftAngle(100 + 1024, 100))).toBeCloseTo(90);
    expect(shaftAngle(100 - 1024, 100)).toBeCloseTo(-Math.PI / 2);
    expect(shaftDegrees(shaftAngle(100 - 1024, 100))).toBeCloseTo(270);
    expect(shaftAngle(100, 100)).toBe(0);
  });
});
