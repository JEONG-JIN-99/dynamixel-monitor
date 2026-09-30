<script setup lang="ts">
import { computed, watch, onUnmounted } from "vue";
import { useRoute } from "vue-router";
import AppHeader from "./components/layout/AppHeader.vue";
import AppSidebar from "./components/layout/AppSidebar.vue";
import { useMotorStore } from "./stores/motorStore";
import { useControlStore } from "./stores/controlStore";
import "./styles/control.css";
import "./styles/dual.css";
import MotorScope from "./components/MotorScope.vue";
import MotorSelector from "./components/MotorSelector.vue";
import { MOTOR_SLOTS, parseMotorSlot } from "./services/motorSlot";
const route = useRoute();
const selected = computed(() => parseMotorSlot(route.query.motor) ?? 1);
for (const slot of MOTOR_SLOTS) {
  const control = useControlStore(slot),
    store = useMotorStore(slot);
  control.start();
  watch(
    () =>
      (control.state?.active
        ? control.state.run?.source
        : control.state?.saved?.source) ??
      control.state?.defaultSource ??
      "mock",
    (source) => {
      const mode = source === "real" ? "csv" : "mock";
      if (store.connection === "disconnected" || store.mode !== mode)
        store.start(mode);
    },
    { immediate: true },
  );
  onUnmounted(() => {
    control.stop();
    store.stop();
  });
}
</script>
<template>
  <div class="shell">
    <AppSidebar />
    <div class="workspace">
      <MotorScope :key="selected" :slot="selected"><AppHeader /></MotorScope>
      <main>
        <div v-if="$route.path === '/control'" class="dual-selection">
          <MotorSelector select />
        </div>
        <MotorScope :key="selected" :slot="selected"><RouterView /></MotorScope>
      </main>
    </div>
  </div>
</template>
