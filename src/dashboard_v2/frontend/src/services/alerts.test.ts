import { describe, expect, it } from "vitest";
import {
  alertContext,
  alertSession,
  alertStatus,
  emptyJournal,
  ingestAlerts,
  restoreJournal,
} from "./alerts";
import type { Sample } from "../types/motor";
const sample = (
  seq: number,
  codes: string[] | null = ["overload"],
  patch: Partial<Sample> = {},
) =>
  ({
    serverSessionId: "server",
    sourceSessionId: "source",
    runId: "run",
    busId: "bus",
    model: "XM430-W210",
    id: 1,
    seq,
    elapsedMs: seq * 100,
    timestamp: 100000 + seq * 100,
    diagnosis:
      codes === null
        ? null
        : { state: codes.length ? "fault" : "normal", codes },
    ...patch,
  }) as Sample;
const session = alertSession("csv", "server", "source", "run");

describe("diagnosis alert episodes", () => {
  it("deduplicates sustained faults and records code additions, partial recovery and recurrence", () => {
    const j = emptyJournal();
    ingestAlerts(j, "csv", [
      sample(1),
      sample(2),
      sample(3, ["overload", "friction", "friction"]),
    ]);
    expect(j.records.map((r) => r.code)).toEqual(["overload", "friction"]);
    ingestAlerts(j, "csv", [sample(4, ["friction"])]);
    expect(j.records[0]!.resolvedAt).toBe(100400);
    expect(j.records[1]!.resolvedAt).toBeNull();
    ingestAlerts(j, "csv", [sample(5, []), sample(6)]);
    expect(j.records).toHaveLength(3);
    expect(j.records[2]).toMatchObject({
      code: "overload",
      read: false,
      resolvedAt: null,
    });
  });
  it("missing, waiting and invalid diagnosis never imply recovery or invent faults", () => {
    const j = emptyJournal();
    ingestAlerts(j, "csv", [
      sample(1),
      sample(2, null),
      sample(3, [], { diagnosis: { state: "waiting", codes: [] } }),
    ]);
    expect(alertStatus(j, j.records[0]!, session, true)).toBe("unknown");
    ingestAlerts(j, "csv", [
      sample(4, [], { diagnosis: { state: "fault", codes: [] } }),
      sample(5, [], { diagnosis: { state: "normal", codes: ["friction"] } }),
      sample(6, [], { diagnosis: { state: "fault", codes: null } as any }),
    ]);
    expect(j.records).toHaveLength(1);
    expect(j.records[0]!.resolvedAt).toBeNull();
    ingestAlerts(j, "csv", [sample(7)]);
    expect(alertStatus(j, j.records[0]!, session, true)).toBe("active");
    expect(alertStatus(j, j.records[0]!, session, false)).toBe("unknown");
  });
  it("keeps motors, buses, runs and sources independent", () => {
    const j = emptyJournal();
    ingestAlerts(j, "csv", [
      sample(1),
      sample(1, ["friction"], { id: 2 }),
      sample(1, ["friction"], { busId: "bus2" }),
    ]);
    ingestAlerts(j, "mock", [sample(1)]);
    ingestAlerts(j, "csv", [sample(2, []), sample(1, [], { runId: "run2" })]);
    expect(j.records.filter((r) => r.resolvedAt === null)).toHaveLength(3);
    expect(j.records[1]!.code).toBe("friction");
    expect(
      alertStatus(
        j,
        j.records[1]!,
        alertSession("csv", "server", "source", "run2"),
        true,
      ),
    ).toBe("unknown");
  });
  it("preserves read flags and checkpoints over restoration and snapshot replay", () => {
    const j = emptyJournal();
    ingestAlerts(j, "csv", [sample(1), sample(2)]);
    j.records[0]!.read = true;
    const restored = restoreJournal(JSON.stringify(j));
    ingestAlerts(restored, "csv", [sample(1), sample(2), sample(3)]);
    expect(restored.records).toHaveLength(1);
    expect(restored.records[0]!.read).toBe(true);
    ingestAlerts(restored, "csv", [sample(4, []), sample(5)]);
    expect(restored.records[1]!.read).toBe(false);
  });
  it("ignores stale and duplicated sequences; never resolves with backward elapsed time", () => {
    const j = emptyJournal();
    ingestAlerts(j, "csv", [sample(5)]);
    ingestAlerts(j, "csv", [
      sample(4, []),
      sample(5, []),
      sample(6, [], { elapsedMs: 1 }),
    ]);
    expect(j.records[0]!.resolvedAt).toBeNull();
    expect(j.cursors[alertContext("csv", sample(5))]!.seq).toBe(5);
  });
  it("retains short episodes inside a long batch, independently of chart retention", () => {
    const j = emptyJournal();
    ingestAlerts(j, "csv", [sample(1), sample(2, []), sample(1000, [])]);
    expect(j.records).toHaveLength(1);
    expect(j.records[0]!.resolvedAt).toBe(100200);
    expect(j.records[0]!.read).toBe(false);
  });
  it("rejects corrupted saved state without trusting arbitrary record shapes", () => {
    expect(restoreJournal(null).records).toEqual([]);
    for (const raw of [
      "{",
      "null",
      '{"version":1,"records":[{}],"cursors":{}}',
    ]) {
      expect(() => restoreJournal(raw)).toThrow();
    }
  });
});
