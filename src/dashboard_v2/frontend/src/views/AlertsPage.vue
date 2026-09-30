<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";
import MotorSelector from "../components/MotorSelector.vue";
import MotorScope from "../components/MotorScope.vue";
import AlertsView from "./AlertsView.vue";
import { useAlertStore } from "../stores/alertStore";
import { CheckCheck } from "lucide-vue-next";
import {
  MOTOR_SLOTS,
  parseMotorSlot,
  type MotorSlot,
} from "../services/motorSlot";
const route = useRoute();
const alerts = new Map(MOTOR_SLOTS.map((slot) => [slot, useAlertStore(slot)]));
const slots = computed<MotorSlot[]>(() =>
  parseMotorSlot(route.query.motor)
    ? [parseMotorSlot(route.query.motor)!]
    : [...MOTOR_SLOTS],
);
const unreadCount = computed(() =>
  slots.value.reduce((count, slot) => count + alerts.get(slot)!.unreadCount, 0),
);
function markAllRead() {
  for (const slot of slots.value) alerts.get(slot)!.markAllRead();
}
</script>
<template>
  <div class="dual-page-heading">
    <h2>알림</h2>
    <div class="alert-page-actions">
      <MotorSelector all select />
      <button class="source-button" :disabled="unreadCount === 0" @click="markAllRead">
        <CheckCheck :size="16" />전체 확인
      </button>
    </div>
  </div>
  <section
    v-for="slot in slots"
    :key="slot"
    class="motor-alert-section"
    :data-motor="slot"
  >
    <MotorScope :slot="slot"><AlertsView /></MotorScope>
  </section>
</template>
<style scoped>
.alert-page-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}
.alert-page-actions button {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}
.alert-page-actions button:disabled {
  opacity: .45;
  cursor: default;
}
</style>
