import { useMotorSlot, motorUrl, type MotorSlot } from "../services/motorSlot";
import { computed, ref, shallowRef } from "vue";
import { defineStore } from "pinia";
import type { Sample, SourceMode } from "../types/motor";
import { alertSession, emptyJournal, ingestAlerts } from "../services/alerts";

function createAlertStore(slot: MotorSlot) {
  return defineStore("alerts-" + slot, () => {
    // Live notifications belong to this page lifetime, never browser storage.
    const journals = {
      csv: shallowRef(emptyJournal()),
      mock: shallowRef(emptyJournal()),
    };
    const sessions: Record<SourceMode, string | null> = {
      csv: null,
      mock: null,
    };
    const source = ref<SourceMode>("csv");
    const session = ref<string | null>(null);
    const current = computed(() => journals[source.value].value);
    const records = computed(() => current.value.records);
    const unreadCount = computed(
      () => records.value.filter((r) => !r.read).length,
    );
    function changed() {
      const target = journals[source.value];
      target.value = { ...target.value, records: [...target.value.records] };
    }
    function markRead(id: string) {
      const record = records.value.find((r) => r.id === id);
      if (!record || record.read) return;
      record.read = true;
      record.readAt = Date.now();
      changed();
    }
    function markAllRead() {
      const unread = records.value.filter((record) => !record.read);
      if (!unread.length) return;
      const now = Date.now();
      for (const record of unread) {
        record.read = true;
        record.readAt = now;
      }
      changed();
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
      const next = alertSession(source.value, server, stream, run);
      if (sessions[source.value] !== next) {
        journals[source.value].value = emptyJournal();
        sessions[source.value] = next;
      }
      session.value = next;
    }
    function ingest(
      samples: Sample[],
      options: { snapshot?: boolean; active?: boolean } = {},
    ) {
      // Snapshots establish a cursor and update known recovery only; never notify.
      // Only newly streamed verdicts during a running/finishing experiment can notify.
      if (!options.snapshot && options.active !== true) return;
      if (
        ingestAlerts(
          current.value,
          source.value,
          samples,
          !options.snapshot && options.active === true,
        )
      )
        changed();
    }
    return {
      current,
      records,
      source,
      session,
      unreadCount,
      start,
      beginSession,
      ingest,
      markRead,
      markAllRead,
    };
  });
}
const stores = new Map<MotorSlot, ReturnType<typeof createAlertStore>>();
export function useAlertStore(slot: MotorSlot = useMotorSlot()) {
  if (!stores.has(slot)) stores.set(slot, createAlertStore(slot));
  return stores.get(slot)!();
}
