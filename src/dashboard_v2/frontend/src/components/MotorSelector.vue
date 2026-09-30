<script setup lang="ts">
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { MOTOR_SLOTS, parseMotorSlot } from "../services/motorSlot";
const props = defineProps<{ all?: boolean; select?: boolean }>();
const route = useRoute(),
  router = useRouter();
const value = computed(() =>
  String(parseMotorSlot(route.query.motor) ?? (props.all ? "all" : 1)),
);
function choose(motor: string) {
  void router.replace({ path: route.path, query: { ...route.query, motor } });
}
</script>
<template>
  <select
    v-if="select"
    class="motor-select"
    :value="value"
    aria-label="모터 선택"
    @change="choose(($event.target as HTMLSelectElement).value)"
  >
    <option v-if="all" value="all">전체</option>
    <option v-for="slot in MOTOR_SLOTS" :key="slot" :value="String(slot)">
      모터 {{ slot }}
    </option>
  </select>
  <div v-else class="motor-tabs" role="group" aria-label="모터 선택">
    <button
      v-if="all"
      class="source-button"
      :aria-pressed="value === 'all'"
      @click="choose('all')"
    >
      전체
    </button>
    <button
      v-for="slot in MOTOR_SLOTS"
      :key="slot"
      class="source-button"
      :aria-pressed="value === String(slot)"
      @click="choose(String(slot))"
    >
      모터 {{ slot }}
    </button>
  </div>
</template>
<style scoped>
.motor-select {
  color-scheme: dark;
  background-color: var(--panel);
  color: var(--text);
  border: 1px solid #35465e;
  border-radius: 7px;
  padding: 10px 12px;
  font: inherit;
}
.motor-select option {
  background-color: var(--panel);
  color: var(--text);
}
.motor-tabs {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.motor-tabs button[aria-pressed="true"] {
  border-color: #59d6b2;
  color: #59d6b2;
  background: #173934;
}
</style>
