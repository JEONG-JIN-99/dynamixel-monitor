import { computed, type ComputedRef } from "vue";
import type { Sample } from "../types/motor";
const references = new Map<string, number>();
export function useShaftPosition(
  history: ComputedRef<Sample[]>,
  context: ComputedRef<string>,
) {
  const origin = computed(() => {
    const samples = history.value;
    const explicit = samples.find(
      (s) =>
        typeof s.basePosition === "number" && Number.isFinite(s.basePosition),
    );
    if (explicit) references.set(context.value, explicit.basePosition!);
    else if (!references.has(context.value)) {
      const first = samples.find(
        (s) => typeof s.position === "number" && Number.isFinite(s.position),
      );
      if (first) references.set(context.value, first.position!);
    }
    // Do not reset the reference when the chart rolls past 60 seconds or the user changes pages.
    return references.get(context.value) ?? null;
  });
  return { origin };
}
