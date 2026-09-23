<script setup lang="ts">
import { watch, onUnmounted } from "vue";
import { useRoute } from "vue-router";
import AppHeader from "./components/layout/AppHeader.vue";
import AppSidebar from "./components/layout/AppSidebar.vue";
import { useMotorStore } from "./stores/motorStore";
const store = useMotorStore();
const route = useRoute();
watch(
  () => (route.query.source === "mock" ? "mock" : "csv"),
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
