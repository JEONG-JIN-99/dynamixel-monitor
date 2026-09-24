import { defineStore } from "pinia";
import { computed, ref, shallowRef } from "vue";
import type { MotorMetadata } from "../types/motor";
export type Config = Record<string, string | number | boolean>;
export interface SavedConfig {
  id: string;
  source: "mock" | "real";
  config: Config;
  savedAt: string;
}
export interface RunRecord {
  runId: string;
  source: "mock" | "real";
  status: string;
  startedAt: string;
  endedAt: string | null;
  date: string;
  motorModel: string;
  motorId: number;
  condition: string;
  elapsedMs: number;
  completedCycles: number;
  rowCount: number;
  sampleIntervalSec: number;
  error: string | null;
  metadata: MotorMetadata[];
}
interface ControlState {
  saved: SavedConfig | null;
  defaults: Config;
  run: RunRecord | null;
  active: boolean;
  externalActive: boolean;
}
export const statusLabel = (status?: string) =>
  ({
    preparing: "준비 중",
    running: "실험 중",
    finishing: "왕복 완료 후 종료",
    completed: "완료",
    failed: "오류",
    interrupted: "중단",
  })[status ?? ""] ?? "대기";
export const conditionLabel = (value: string) =>
  ({
    normal: "정상",
    friction: "마찰",
    overload: "과부하",
    overvoltage: "과전압",
    undervoltage: "과소전압",
    undercurrent: "과소전류",
    gear_backlash: "기어 백래시",
  })[value] ?? value;
export const useControlStore = defineStore("control", () => {
  const state = shallowRef<ControlState | null>(null),
    error = ref(""),
    busy = ref(false),
    connected = ref(false);
  let revision = 0;
  let timer: ReturnType<typeof setTimeout> | undefined,
    stopped = true;
  async function refresh() {
    if (busy.value) return;
    const requestedRevision = revision;
    try {
      const response = await fetch("/api/control", { cache: "no-store" });
      if (!response.ok) throw Error();
      const next = await response.json();
      if (!busy.value && requestedRevision === revision) state.value = next;
      connected.value = true;
    } catch {
      connected.value = false;
    }
  }
  async function poll() {
    await refresh();
    if (!stopped) timer = setTimeout(poll, 1000);
  }
  function start() {
    if (!stopped) return;
    stopped = false;
    void poll();
  }
  function stop() {
    stopped = true;
    clearTimeout(timer);
  }
  async function action(path: string, body: unknown) {
    if (busy.value) return false;
    busy.value = true;
    revision++;
    error.value = "";
    try {
      const response = await fetch(`/api/control/${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const value = await response.json();
      if (!response.ok)
        throw Error(
          typeof value.detail === "string"
            ? value.detail
            : "요청을 처리하지 못했습니다",
        );
      state.value = value;
      connected.value = true;
      return true;
    } catch (e) {
      error.value = e instanceof Error ? e.message : "연결을 확인하세요";
      return false;
    } finally {
      busy.value = false;
    }
  }
  return {
    state,
    error,
    busy,
    connected,
    refresh,
    start,
    stop,
    action,
    active: computed(() => !!state.value?.active),
  };
});
