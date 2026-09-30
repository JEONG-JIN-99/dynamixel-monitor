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
it("ignores stored alerts and all snapshot faults, accepting only live active verdicts", () => {
  localStorage.setItem(
    "motor-dashboard.mock-diagnosis-alerts.v1",
    JSON.stringify({
      version: 1,
      records: [
        { read: false },
        { read: false },
        { read: false },
        { read: false },
      ],
      cursors: {},
    }),
  );
  const store = useAlertStore();
  store.start("mock");
  store.beginSession("server", "run:1", "run");
  expect(store.unreadCount).toBe(0);
  store.ingest([row(1, ["friction"]), row(2, ["overload"])], {
    snapshot: true,
    active: true,
  });
  expect(store.records).toHaveLength(0);
  store.ingest([row(3, ["friction"])], { active: false });
  expect(store.unreadCount).toBe(0);
  store.ingest([row(4, ["overload"])], { active: true });
  expect(store.unreadCount).toBe(1);
  store.ingest([row(5, ["overload"])], { active: true });
  expect(store.unreadCount).toBe(1);
  store.markRead(store.records[0]!.id);
  store.beginSession("server", "run:1", "run");
  store.ingest([row(6, [])], { snapshot: true, active: true });
  expect(store.records[0]!.read).toBe(true);
  expect(store.records[0]!.resolvedAt).toBe(100600);
  store.ingest([row(7, ["overload"])], { active: true });
  expect(store.unreadCount).toBe(1);
  store.beginSession("server", "next:1", "next");
  expect(store.records).toHaveLength(0);
});
it("reload never restores live alerts or acknowledgment state", () => {
  const store = useAlertStore();
  store.start("csv");
  store.ingest([row(1, ["overload"])], { active: true });
  expect(store.unreadCount).toBe(1);
  setActivePinia(createPinia());
  const fresh = useAlertStore();
  fresh.start("csv");
  fresh.ingest([row(1, ["overload"])], { snapshot: true, active: true });
  expect(fresh.unreadCount).toBe(0);
});
it("snapshot recovery does not confirm existing unread alerts", () => {
  const store = useAlertStore();
  store.start("csv");
  store.ingest([row(1, ["overload"])], { active: true });
  store.ingest([row(2, [])], { snapshot: true, active: false });
  expect(store.records[0]!.resolvedAt).toBe(100200);
  expect(store.unreadCount).toBe(1);
});
it("bulk confirmation preserves history and active faults, with independent motors and new alerts", () => {
  const one = useAlertStore(1), two = useAlertStore(2);
  for (const store of [one, two]) {
    store.start("mock");
    store.beginSession("server", "run:1", "run");
    store.ingest([row(1, ["friction", "overload"])], { active: true });
  }
  one.markRead(one.records[0]!.id);
  const originalReadAt = one.records[0]!.readAt;
  vi.advanceTimersByTime(1000);
  one.markAllRead();
  expect(one.unreadCount).toBe(0);
  expect(two.unreadCount).toBe(2);
  expect(one.records).toHaveLength(2);
  expect(one.records[0]!.readAt).toBe(originalReadAt);
  expect(one.records.every((record) => record.resolvedAt == null)).toBe(true);
  const confirmedAt = one.records.map((record) => record.readAt);
  vi.advanceTimersByTime(1000);
  one.markAllRead();
  expect(one.records.map((record) => record.readAt)).toEqual(confirmedAt);
  one.ingest([row(2, ["friction", "overload"])], { active: true });
  expect(one.unreadCount).toBe(0);
  one.ingest([row(3, [])], { active: true });
  one.ingest([row(4, ["overload"])], { active: true });
  expect(one.unreadCount).toBe(1);
});
