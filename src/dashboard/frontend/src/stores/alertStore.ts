import { computed, ref, shallowRef } from "vue";
import { defineStore } from "pinia";
import type { Sample, SourceMode } from "../types/motor";
import {
  ALERT_STORAGE_KEY,
  MOCK_ALERT_STORAGE_KEY,
  alertContext,
  alertSession,
  emptyJournal,
  ingestAlerts,
  restoreJournal,
} from "../services/alerts";

export const useAlertStore = defineStore("alerts", () => {
  const storageWarning = ref("");
  function load(key: string) {
    try {
      return restoreJournal(localStorage.getItem(key));
    } catch {
      storageWarning.value =
        "저장된 알림을 불러오지 못했습니다. 새 알림은 계속 표시합니다.";
      return emptyJournal();
    }
  }
  const journal = shallowRef(load(ALERT_STORAGE_KEY));
  const demo = shallowRef(load(MOCK_ALERT_STORAGE_KEY));
  const source = ref<SourceMode>("csv");
  const session = ref<string | null>(null);
  const current = computed(() =>
    source.value === "mock" ? demo.value : journal.value,
  );
  const records = computed(() => current.value.records);
  const unreadCount = computed(
    () => records.value.filter((r) => !r.read).length,
  );
  let timer: ReturnType<typeof setTimeout> | undefined;

  const pending = new Set<SourceMode>();
  function persist() {
    clearTimeout(timer);
    timer = undefined;
    try {
      for (const mode of pending) {
        localStorage.setItem(
          mode === "mock" ? MOCK_ALERT_STORAGE_KEY : ALERT_STORAGE_KEY,
          JSON.stringify(mode === "mock" ? demo.value : journal.value),
        );
      }
      pending.clear();
      storageWarning.value = "";
    } catch {
      storageWarning.value =
        "알림을 브라우저에 저장하지 못했습니다. 현재 화면의 기록은 유지되지만 새로고침하면 사라질 수 있습니다.";
    }
  }
  function changed(immediate = false) {
    const target = source.value === "mock" ? demo : journal;
    target.value = { ...target.value, records: [...target.value.records] };
    pending.add(source.value);
    if (immediate) persist();
    else if (!timer) timer = setTimeout(persist, 500);
  }
  function markRead(id: string) {
    const record = records.value.find((r) => r.id === id);
    if (!record || record.read) return;
    record.read = true;
    record.readAt = Date.now();
    changed(true);
  }
  function start(mode: SourceMode) {
    source.value = mode;
    session.value = null;
  }
  function beginSession(
    server: string,
    stream: string | null,
    run: string | null,
  ) {
    session.value = alertSession(source.value, server, stream, run);
  }
  function ingest(
    samples: Sample[],
    options: { snapshot?: boolean; active?: boolean } = {},
  ) {
    const active = options.active ?? true;
    const latest = new Map<string, number>();
    if (options.snapshot && active) {
      for (const sample of samples) {
        const key = alertContext(source.value, sample);
        latest.set(key, Math.max(latest.get(key) ?? -1, sample.seq));
      }
    }
    const notify = options.snapshot
      ? (sample: Sample) =>
          active &&
          latest.get(alertContext(source.value, sample)) === sample.seq
      : active;
    if (ingestAlerts(current.value, source.value, samples, notify)) changed();
  }
  if (typeof window !== "undefined") {
    window.addEventListener("pagehide", () => {
      if (timer) persist();
    });
    document.addEventListener("visibilitychange", () => {
      if (document.hidden && timer) persist();
    });
  }
  return {
    current,
    records,
    source,
    session,
    unreadCount,
    storageWarning,
    start,
    beginSession,
    ingest,
    markRead,
  };
});
