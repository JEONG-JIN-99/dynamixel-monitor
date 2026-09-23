import { computed, ref, shallowRef } from "vue";
import { defineStore } from "pinia";
import type { Sample, SourceMode } from "../types/motor";
import {
  ALERT_STORAGE_KEY,
  alertSession,
  emptyJournal,
  ingestAlerts,
  restoreJournal,
} from "../services/alerts";

export const useAlertStore = defineStore("alerts", () => {
  const storageWarning = ref("");
  function load() {
    try {
      return restoreJournal(localStorage.getItem(ALERT_STORAGE_KEY));
    } catch {
      storageWarning.value =
        "저장된 알림을 불러오지 못했습니다. 새 알림은 계속 표시합니다.";
      return emptyJournal();
    }
  }
  const journal = shallowRef(load());
  const demo = shallowRef(emptyJournal());
  const source = ref<SourceMode>("csv");
  const session = ref<string | null>(null);
  const viewing = ref(false);
  const current = computed(() =>
    source.value === "mock" ? demo.value : journal.value,
  );
  const records = computed(() => current.value.records);
  const unreadCount = computed(
    () => records.value.filter((r) => !r.read).length,
  );
  let timer: ReturnType<typeof setTimeout> | undefined;

  function persist() {
    clearTimeout(timer);
    timer = undefined;
    try {
      localStorage.setItem(ALERT_STORAGE_KEY, JSON.stringify(journal.value));
      storageWarning.value = "";
    } catch {
      storageWarning.value =
        "알림을 브라우저에 저장하지 못했습니다. 현재 화면의 기록은 유지되지만 새로고침하면 사라질 수 있습니다.";
    }
  }
  function changed(immediate = false) {
    const target = source.value === "mock" ? demo : journal;
    target.value = { ...target.value, records: [...target.value.records] };
    if (source.value === "mock") return;
    if (immediate) persist();
    else if (!timer) timer = setTimeout(persist, 500);
  }
  function markAllRead() {
    let dirty = false;
    for (const r of records.value)
      if (!r.read) {
        r.read = true;
        dirty = true;
      }
    if (dirty) changed(true);
  }
  function setViewing(visible: boolean) {
    viewing.value = visible;
    if (visible) markAllRead();
  }
  function start(mode: SourceMode) {
    source.value = mode;
    session.value = null;
    if (mode === "mock") demo.value = emptyJournal();
    if (viewing.value) markAllRead();
  }
  function beginSession(
    server: string,
    stream: string | null,
    run: string | null,
  ) {
    session.value = alertSession(source.value, server, stream, run);
  }
  function ingest(samples: Sample[]) {
    if (ingestAlerts(current.value, source.value, samples, viewing.value))
      changed();
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
    setViewing,
    markAllRead,
  };
});
