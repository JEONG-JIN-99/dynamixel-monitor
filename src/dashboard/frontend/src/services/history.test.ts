import { connectMotorData } from "./motorDataService";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { mergeHistory } from "./history";
import type { Sample, Snapshot } from "../types/motor";
vi.mock("./motorDataService", () => ({
  connectMotorData: vi.fn(() => vi.fn()),
}));
import { useMotorStore } from "../stores/motorStore";

const sample = (seq: number, elapsedMs: number, source = "r:1") =>
  ({
    seq,
    elapsedMs,
    serverSessionId: "server",
    sourceSessionId: source,
    runId: "r",
  }) as Sample;
const snapshot = (overrides: Partial<Snapshot> = {}): Snapshot => ({
  serverSessionId: "server",
  sourceSessionId: "r:1",
  runId: "r",
  experiment: { runId: "r" } as Snapshot["experiment"],
  metadata: [],
  latest: null,
  history: [],
  retentionSec: 60,
  capacity: 12000,
  seq: 0,
  events: [],
  system: {
    sourceMode: "csv",
    validity: "valid",
    experimentStatus: "running",
    dataAgeSec: 0,
    configuredHz: 10,
    observedHz: 10,
    expectedFlushSec: 2,
    error: null,
    readerCaughtUp: true,
  },
  ...overrides,
});
describe("CSV telemetry history", () => {
  beforeEach(() => setActivePinia(createPinia()));
  it("retains 60 seconds at original measurement times across a batch", () => {
    const result = mergeHistory(
      [],
      Array.from({ length: 801 }, (_, i) => sample(i, i * 100)),
    );
    expect(result).toHaveLength(601);
    expect(result[0]?.elapsedMs).toBe(20000);
    expect(result.at(-1)?.elapsedMs).toBe(80000);
  });
  it("deduplicates without filling rejected CSV row gaps", () => {
    expect(
      mergeHistory([sample(1, 0)], [sample(1, 0), sample(3, 200)]),
    ).toEqual([sample(1, 0), sample(3, 200)]);
  });
  it("freezes measurement history when a stale system message arrives", () => {
    const store = useMotorStore();
    const snap = snapshot({ history: [sample(1, 0)] });
    store.accept({ schemaVersion: 1, type: "snapshot", ...snap });
    store.accept({
      schemaVersion: 1,
      type: "system",
      serverSessionId: "server",
      sourceSessionId: "r:1",
      system: { ...snap.system, validity: "stale" },
      experiment: snap.experiment,
      metadata: [],
    });
    expect(store.history).toEqual([sample(1, 0)]);
    expect(store.live).toBe(false);
  });
  it("resets history and rejects messages from an old file generation", () => {
    const store = useMotorStore();
    store.accept({
      schemaVersion: 1,
      type: "snapshot",
      ...snapshot({ history: [sample(1, 0)] }),
    });
    store.accept({
      schemaVersion: 1,
      type: "reset",
      ...snapshot({ sourceSessionId: "r:2" }),
    });
    store.accept({
      schemaVersion: 1,
      type: "samples",
      serverSessionId: "server",
      sourceSessionId: "r:1",
      samples: [sample(2, 100)],
    });
    expect(store.history).toHaveLength(0);
  });
  it("accepts reboot snapshot with new server session and rejects old samples", () => {
    const store = useMotorStore();
    store.accept({
      schemaVersion: 1,
      type: "snapshot",
      ...snapshot({
        serverSessionId: "new-server",
        history: [sample(10, 1000)],
      }),
    });
    store.accept({
      schemaVersion: 1,
      type: "samples",
      serverSessionId: "server",
      sourceSessionId: "r:1",
      samples: [sample(11, 1100)],
    });
    expect(store.history).toHaveLength(1);
  });
  it("clears mock data when switching to CSV; no mock fallback", () => {
    const store = useMotorStore();
    store.start("mock");
    store.accept({
      schemaVersion: 1,
      type: "snapshot",
      ...snapshot({ history: [sample(1, 0)] }),
    });
    store.start("csv");
    expect(store.mode).toBe("csv");
    expect(store.history).toEqual([]);
    expect(store.system.validity).toBe("waiting");
  });
});

it("ignores messages and connection callbacks from a source that was replaced", () => {
  setActivePinia(createPinia());
  const store = useMotorStore();
  store.start("mock");
  const previous = vi.mocked(connectMotorData).mock.calls.at(-1)!;
  store.start("csv");
  const current = vi.mocked(connectMotorData).mock.calls.at(-1)!;
  current[2]("connecting");
  previous[1]({
    schemaVersion: 1,
    type: "snapshot",
    ...snapshot({ history: [sample(1, 0)] }),
  });
  previous[2]("connected");
  expect(store.mode).toBe("csv");
  expect(store.history).toEqual([]);
  expect(store.system.sourceMode).toBe("csv");
  expect(store.connection).toBe("connecting");
});
