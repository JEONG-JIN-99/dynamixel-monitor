<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRoute } from "vue-router";
import { useMotorStore } from "../../stores/motorStore";
const store = useMotorStore();
const route = useRoute();
const clock = ref(new Date());
let timer: ReturnType<typeof setInterval>;
onMounted(() => {
  timer = setInterval(() => (clock.value = new Date()), 1000);
});
onUnmounted(() => clearInterval(timer));
const badge = computed(() => {
  if (route.params.runId) return "실험 기록";
  if (store.mode === "mock")
    return store.connection === "connected" ? "연결됨" : "연결 대기";
  if (store.connection !== "connected") return "연결 대기";
  if (store.live) return "수신 중";
  if (
    ["completed", "interrupted", "failed"].includes(
      store.system.experimentStatus,
    )
  )
    return "수집 종료";
  return {
    valid: "수신 완료",
    waiting: "데이터 대기",
    stale: "갱신 지연",
    error: "연결 오류",
  }[store.system.validity];
});
</script>
<template>
  <header class="app-header">
    <h1>모터 모니터링</h1>
    <div class="header-tools">
      <span
        class="connection-badge"
        :class="{ live: store.connection === 'connected' }"
        ><i class="dot"></i>{{ badge }}</span
      >
      <time class="clock" :datetime="clock.toISOString()"
        >{{ clock.toLocaleDateString("sv-SE").replaceAll("-", ".")
        }}<span>{{
          clock.toLocaleTimeString("ko-KR", { hour12: false })
        }}</span></time
      >
    </div>
  </header>
</template>
