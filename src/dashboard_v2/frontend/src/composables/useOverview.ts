import { computed, onUnmounted, ref, shallowRef, watch } from "vue";
import { useMotorStore } from "../stores/motorStore";
import { motorKey, SCREEN_INTERVAL_MS } from "../services/overview";
import type { Sample } from "../types/motor";

// Transport state stays in the store; screen updates consume all received samples every 100 ms.
export function useOverview() {
  const store = useMotorStore();
  const renderedHistory = shallowRef<Sample[]>(store.history);
  const selection = ref("");
  const options = computed(() => {
    const motors = new Map<string, { model: string; id: number }>();
    for (const motor of [...store.metadata, ...renderedHistory.value])
      motors.set(motorKey(motor), { model: motor.model, id: motor.id });
    return Array.from(motors.values());
  });
  const selectedKey = computed({
    get: () =>
      options.value.some((m) => motorKey(m) === selection.value)
        ? selection.value
        : options.value[0]
          ? motorKey(options.value[0])
          : "",
    set: (value: string) => {
      selection.value = value;
    },
  });
  const selectedMotor = computed(() =>
    options.value.find((m) => motorKey(m) === selectedKey.value),
  );
  const history = computed(() =>
    renderedHistory.value.filter((row) => motorKey(row) === selectedKey.value),
  );
  const latest = computed(() => history.value.at(-1) ?? null);
  const timer = setInterval(() => {
    if (renderedHistory.value !== store.history)
      renderedHistory.value = store.history;
  }, SCREEN_INTERVAL_MS);
  // Never leave mock/previous-run values visible while changing the source.
  watch(
    () => [store.mode, store.experiment?.runId],
    () => {
      renderedHistory.value = store.history;
    },
    { flush: "sync" },
  );
  onUnmounted(() => clearInterval(timer));
  return { store, options, selectedKey, selectedMotor, history, latest };
}
