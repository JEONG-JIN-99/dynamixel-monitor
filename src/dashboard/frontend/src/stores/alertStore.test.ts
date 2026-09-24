import { beforeEach, afterEach, it, expect, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { useAlertStore } from "./alertStore";
import type { Sample } from "../types/motor";
const row = (seq: number, codes: string[]) =>
  ({
    serverSessionId: "server",
    sourceSessionId: "run:1",
    runId: "run",
    busId: "mock",
    id: 1,
    model: "XM430-W210",
    seq,
    elapsedMs: seq * 100,
    timestamp: 100000 + seq * 100,
    receivedAt: 100000 + seq * 100,
    diagnosis: { state: codes.length ? "fault" : "normal", codes },
  }) as Sample;
beforeEach(() => {
  vi.useFakeTimers();
  const values = new Map<string, string>();
  vi.stubGlobal("localStorage", {
    getItem: (k: string) => values.get(k) ?? null,
    setItem: (k: string, v: string) => values.set(k, v),
  });
  setActivePinia(createPinia());
});
afterEach(() => {
  vi.runOnlyPendingTimers();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});
it("completed snapshot never re-notifies its four old faults", () => {
  const store = useAlertStore();
  store.start("mock");
  const history = [
    row(1, ["friction"]),
    row(2, ["overload"]),
    row(3, []),
    row(4, ["friction"]),
    row(5, ["overload"]),
    row(6, []),
  ];
  store.ingest(history, { snapshot: true, active: false });
  expect(store.unreadCount).toBe(0);
  expect(store.records).toHaveLength(0);
  vi.runOnlyPendingTimers();
  setActivePinia(createPinia());
  const restored = useAlertStore();
  restored.start("mock");
  restored.ingest(history, { snapshot: true, active: false });
  expect(restored.unreadCount).toBe(0);
});
it("only current active faults notify on first snapshot, and mock confirmations persist", () => {
  const store = useAlertStore();
  store.start("mock");
  const history = [row(1, ["overload"]), row(2, []), row(3, ["friction"])];
  store.ingest(history, { snapshot: true, active: true });
  expect(store.records.map((r) => r.code)).toEqual(["friction"]);
  expect(store.unreadCount).toBe(1);
  store.markRead(store.records[0]!.id);
  expect(store.records[0]!.readAt).toBeTypeOf("number");
  store.start("csv");
  expect(store.unreadCount).toBe(0);
  store.start("mock");
  expect(store.records[0]!.read).toBe(true);
  setActivePinia(createPinia());
  const restored = useAlertStore();
  restored.start("mock");
  restored.ingest(history, { snapshot: true, active: true });
  expect(restored.records).toHaveLength(1);
  expect(restored.unreadCount).toBe(0);
  restored.ingest([row(4, []), row(5, ["friction"])]);
  expect(restored.unreadCount).toBe(1);
  expect(restored.records).toHaveLength(2);
});
it("snapshot updates recorded recovery without confirming an unread alert", () => {
  const store = useAlertStore();
  store.start("csv");
  store.ingest([row(1, ["overload"])]);
  store.ingest([row(1, ["overload"]), row(2, [])], {
    snapshot: true,
    active: false,
  });
  expect(store.unreadCount).toBe(1);
  expect(store.records[0]!.resolvedAt).toBe(100200);
  expect(store.records[0]!.read).toBe(false);
});
