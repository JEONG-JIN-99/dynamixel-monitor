<script setup lang="ts">
import { watch, onUnmounted } from "vue";
import { useRoute } from "vue-router";
import AppHeader from "./components/layout/AppHeader.vue";
import AppSidebar from "./components/layout/AppSidebar.vue";
import { useMotorStore } from "./stores/motorStore";
import { useControlStore } from "./stores/controlStore";
import "./styles/control.css";
const control = useControlStore();
control.start();
onUnmounted(control.stop);
const store = useMotorStore();
const route = useRoute();
watch(
  () => (route.query.source === "csv" ? "csv" : "mock"),
  (source) => store.start(source),
  { immediate: true },
);
onUnmounted(store.stop);
</script>
<template>
  <div class="shell">
    <AppSidebar />
    <div class="workspace">
      <AppHeader />
      <main><RouterView /></main>
    </div>
  </div>
</template>
