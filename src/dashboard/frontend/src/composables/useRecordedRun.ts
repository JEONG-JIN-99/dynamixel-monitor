import {
  computed,
  shallowRef,
  ref,
  watch,
  onBeforeUnmount,
  type Ref,
} from "vue";
import { analysisHistory } from "../services/analysis";
import type { HistoryReply } from "../services/analysisHistory";
import type { RunRecord } from "../stores/controlStore";
import type { AnalysisPoint } from "../types/analysis";
export function useRecordedRun(runId: Ref<string>, duration: Ref<number>) {
  const record = shallowRef<RunRecord | null>(null),
    points = shallowRef<AnalysisPoint[]>([]),
    loading = ref(false),
    error = ref("");
  let request: AbortController | undefined;
  async function reload() {
    request?.abort();
    const current = new AbortController();
    request = current;
    points.value = [];
    error.value = "";
    loading.value = false;
    if (!runId.value) {
      record.value = null;
      return;
    }
    loading.value = true;
    const id = runId.value;
    try {
      if (record.value?.runId !== id) {
        record.value = null;
        const response = await fetch(`/api/runs/${encodeURIComponent(id)}`, {
          signal: current.signal,
        });
        if (!response.ok) throw Error();
        const data = await response.json();
        if (current.signal.aborted) return;
        record.value = data;
      }
      const response = await fetch(
        `/api/runs/${encodeURIComponent(id)}/history?durationSec=${duration.value}`,
        { signal: current.signal, cache: "no-store" },
      );
      if (!response.ok) throw Error();
      const data: HistoryReply = await response.json();
      if (current.signal.aborted) return;
      if (data.runId !== id) throw Error();
      points.value = analysisHistory(data.samples, record.value?.metadata[0]);
    } catch {
      if (!current.signal.aborted)
        error.value = "실험 기록을 불러오지 못했습니다";
    } finally {
      if (!current.signal.aborted) loading.value = false;
    }
  }
  watch([runId, duration], reload, { immediate: true });
  onBeforeUnmount(() => request?.abort());
  return {
    record,
    points,
    loading,
    error,
    reload,
    metadata: computed(() => record.value?.metadata[0]),
  };
}
