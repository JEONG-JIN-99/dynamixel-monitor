import {
  computed,
  onBeforeUnmount,
  ref,
  shallowRef,
  watch,
  type Ref,
} from "vue";
import { useMotorStore } from "../stores/motorStore";
import { analysisHistory } from "../services/analysis";
import { motorKey } from "../services/overview";
import {
  appendRecords,
  type AnalysisRecord,
  type HistoryReply,
} from "../services/analysisHistory";
import type { Sample, RegisterSample } from "../types/motor";

export function useAnalysisHistory(
  selectedKey: Ref<string>,
  duration: Ref<number>,
  enabled: Ref<boolean> = ref(true),
) {
  const store = useMotorStore();
  const records = shallowRef<AnalysisRecord[]>([]);
  const loading = ref(false),
    error = ref("");
  const snapshotVersion = ref(0);
  let pending: AnalysisRecord[] = [];
  let request: AbortController | undefined;
  let generation = 0,
    lastContext = "";
  function decode(samples: (Sample | RegisterSample)[]) {
    const selected = samples.filter(
      (s) =>
        motorKey(s) === selectedKey.value &&
        s.runId === store.experiment?.runId &&
        s.sourceSessionId === store.sourceSession &&
        s.serverSessionId === store.serverSession,
    );
    const metadata = store.metadata.find(
      (m) => motorKey(m) === selectedKey.value,
    );
    const points = analysisHistory(selected, metadata);
    return selected.map((sample, i) => ({
      seq: sample.seq,
      point: points[i]!,
    }));
  }
  const unsubscribe = store.subscribeSamples((samples, reset) => {
    if (!enabled.value) return;
    if (reset) snapshotVersion.value++;
    if (duration.value === 60) return;
    pending.push(...decode(samples));
  });
  async function reload() {
    const current = ++generation;
    request?.abort();
    request = new AbortController();
    const controller = request;
    const context = [
      store.mode,
      store.serverSession,
      store.sourceSession,
      store.experiment?.runId,
      selectedKey.value,
      duration.value,
    ].join("|");
    if (context !== lastContext) records.value = [];
    lastContext = context;
    pending = [];
    error.value = "";
    loading.value = false;
    if (
      !enabled.value ||
      duration.value === 60 ||
      !store.experiment?.runId ||
      !store.sourceSession ||
      !selectedKey.value
    )
      return;
    loading.value = true;
    pending = decode(store.history);
    const motor =
      store.metadata.find((m) => motorKey(m) === selectedKey.value) ??
      store.history.find((m) => motorKey(m) === selectedKey.value);
    if (!motor) {
      loading.value = false;
      return;
    }
    const params = new URLSearchParams({
      source: store.mode,
      runId: store.experiment.runId,
      sourceSessionId: store.sourceSession,
      durationSec: String(duration.value),
      motorId: String(motor.id),
      model: motor.model,
    });
    const expectedSession = store.serverSession;
    try {
      const response = await fetch(`/api/history?${params}`, {
        signal: controller.signal,
        cache: "no-store",
      });
      if (!response.ok) throw new Error("History unavailable");
      const result = (await response.json()) as HistoryReply;
      if (current !== generation) return;
      if (
        result.schemaVersion !== 1 ||
        result.runId !== store.experiment?.runId ||
        result.sourceSessionId !== store.sourceSession ||
        result.serverSessionId !== expectedSession
      )
        throw new Error("History session changed");
      const loaded = decode(result.samples);
      records.value = appendRecords(
        loaded,
        pending.sort((a, b) => a.seq - b.seq),
        duration.value,
      );
      pending = [];
    } catch {
      if (current === generation && !controller.signal.aborted)
        error.value = "기록을 불러오지 못했습니다";
    } finally {
      if (current === generation) loading.value = false;
    }
  }
  // A reconnect snapshot reloads the archive, including gaps longer than 60 seconds.
  watch(
    () => [
      duration.value,
      selectedKey.value,
      store.mode,
      store.serverSession,
      store.sourceSession,
      store.experiment?.runId,
      snapshotVersion.value,
      enabled.value,
    ],
    reload,
    { immediate: true },
  );
  const timer = setInterval(() => {
    if (loading.value || !pending.length || duration.value === 60) return;
    records.value = appendRecords(records.value, pending, duration.value);
    pending = [];
  }, 100);
  onBeforeUnmount(() => {
    ++generation;
    request?.abort();
    unsubscribe();
    clearInterval(timer);
    pending = [];
  });
  return {
    points: computed(() => records.value.map((r) => r.point)),
    loading,
    error,
    reload,
  };
}
