<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useMotorStore } from "../../stores/motorStore";
import type { SourceMode } from "../../types/motor";
const store = useMotorStore();
const route = useRoute();
const router = useRouter();
const clock = ref(new Date());
let timer: ReturnType<typeof setInterval>;
onMounted(() => {
  timer = setInterval(() => (clock.value = new Date()), 1000);
});
onUnmounted(() => clearInterval(timer));
const badge = computed(() => {
  if (store.mode === "mock")
    return store.connection === "connected"
      ? "가상 데이터 · 서버 수신"
      : "가상 데이터 · 연결 대기";
  if (store.metadata.some((m) => m.simulated)) return "시연 CSV";
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
function selectSource(source: SourceMode) {
  const query = { ...route.query };
  if (source === "mock") query.source = "mock";
  else delete query.source;
  void router.replace({ path: route.path, query, hash: route.hash });
}
</script>
<template>
  <header class="app-header">
    <h1>모터 모니터링</h1>
    <div class="header-tools">
      <span
        class="connection-badge"
        :class="{ simulated: store.mode === 'mock', live: store.live }"
        ><i class="dot"></i>{{ badge }}</span
      >
      <div class="source-selector" role="group" aria-label="데이터 소스 선택">
        <button
          :aria-pressed="store.mode === 'csv'"
          aria-label="실험 CSV로 돌아가기"
          @click="selectSource('csv')"
        >
          실험 CSV
        </button>
        <button
          :aria-pressed="store.mode === 'mock'"
          aria-label="가상 데이터 보기"
          @click="selectSource('mock')"
        >
          가상 데이터
        </button>
      </div>
      <time class="clock" :datetime="clock.toISOString()"
        >{{ clock.toLocaleDateString("sv-SE").replaceAll("-", ".")
        }}<span>{{
          clock.toLocaleTimeString("ko-KR", { hour12: false })
        }}</span></time
      >
    </div>
  </header>
</template>
