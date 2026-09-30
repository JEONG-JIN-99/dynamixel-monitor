import { describe, expect, it } from "vitest";
import { fleetStatus } from "./fleetStatus";
import type { Sample } from "../types/motor";
const sample = (extra: Partial<Sample> = {}) =>
  ({
    moving: false,
    hwError: 0,
    diagnosis: { state: "normal", codes: [] },
    ...extra,
  }) as Sample;
describe("power, movement and diagnosis are independent", () => {
  it("does not show retained motion or faults after shutdown", () => {
    const last = sample({ moving: true, hwError: 4, diagnosis: { state: "fault", codes: ["overload"] } });
    expect(fleetStatus({ power: "off", moving: null }, last, true))
      .toMatchObject({ moving: null, diagnosis: "전원 꺼짐", powerLabel: "꺼짐", tone: "off", diagnosisTone: "muted" });
    expect(fleetStatus({ power: "unknown", moving: null }, last, true))
      .toMatchObject({ power: "unknown", moving: null });
  });
  it("keeps stopped powered motors distinct from switched off motors", () => {
    expect(
      fleetStatus({ power: "on", moving: false }, sample(), true),
    ).toMatchObject({
      tone: "idle",
      diagnosis: "정상",
      powerLabel: "켜짐",
      movement: "멈춤",
    });
    expect(
      fleetStatus({ power: "off", moving: null }, sample(), true),
    ).toMatchObject({ tone: "off", diagnosis: "전원 꺼짐" });
  });
  it("never infers power loss from disconnection or missing observation", () => {
    expect(fleetStatus(undefined, null, true).tone).toBe("unknown");
    expect(
      fleetStatus({ power: "on", moving: true }, sample(), false).power,
    ).toBe("unknown");
  });
  it("keeps faults red even when motion has stopped", () => {
    expect(
      fleetStatus(
        { power: "on", moving: false },
        sample({ diagnosis: { state: "fault", codes: ["friction"] } }),
        true,
      ),
    ).toMatchObject({ tone: "fault", movement: "멈춤", diagnosis: "마찰" });
    expect(
      fleetStatus({ power: "on", moving: true }, sample({ hwError: 4 }), true)
        .tone,
    ).toBe("fault");
  });
  it("does not infer normal from movement alone", () => {
    expect(fleetStatus({ power: "on", moving: false }, sample({ diagnosis: null }), true).tone)
      .toBe("unknown");
    expect(
      fleetStatus(
        { power: "on", moving: true },
        sample({ moving: true, diagnosis: null }),
        true,
      ).tone,
    ).toBe("unknown");
  });
});
