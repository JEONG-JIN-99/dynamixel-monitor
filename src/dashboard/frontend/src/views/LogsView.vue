<script setup lang="ts">
import { computed, ref, watch, onBeforeUnmount } from "vue";
import { RefreshCw } from "lucide-vue-next";
import {
  type RunRecord,
  statusLabel,
  conditionLabel,
} from "../stores/controlStore";
const year = ref(""),
  month = ref(""),
  day = ref(""),
  source = ref(""),
  offset = ref(0),
  total = ref(0),
  dates = ref<string[]>([]),
  runs = ref<RunRecord[]>([]),
  loading = ref(false),
  error = ref("");
let request: AbortController | undefined;
const years = computed(() => [
  ...new Set(dates.value.map((d) => d.slice(0, 4))),
]);
const months = computed(() =>
  [
    ...new Set(
      dates.value
        .filter((d) => !year.value || d.startsWith(year.value))
        .map((d) => d.slice(5, 7)),
    ),
  ].sort(),
);
const days = computed(() =>
  [
    ...new Set(
      dates.value
        .filter(
          (d) =>
            (!year.value || d.startsWith(year.value)) &&
            (!month.value || d.slice(5, 7) === month.value),
        )
        .map((d) => d.slice(8, 10)),
    ),
  ].sort(),
);
const formatTime = (value: string) =>
  new Date(value).toLocaleString("ko-KR", {
    timeZone: "Asia/Seoul",
    hour12: false,
  });
const terminal = (run: RunRecord) =>
  ["completed", "failed", "interrupted"].includes(run.status);
async function reload() {
  request?.abort();
  const current = new AbortController();
  request = current;
  loading.value = true;
  error.value = "";
  const params = new URLSearchParams({
    offset: String(offset.value),
    limit: "30",
  });
  for (const [key, value] of Object.entries({
    year: year.value,
    month: month.value,
    day: day.value,
    source: source.value,
  }))
    if (value) params.set(key, value);
  try {
    const response = await fetch(`/api/runs?${params}`, {
      signal: current.signal,
      cache: "no-store",
    });
    if (!response.ok) throw Error();
    const data = await response.json();
    if (current.signal.aborted) return;
    runs.value = data.runs;
    total.value = data.total;
    dates.value = data.dates;
  } catch {
    if (!current.signal.aborted) error.value = "기록을 불러오지 못했습니다";
  } finally {
    if (!current.signal.aborted) loading.value = false;
  }
}
watch(year, () => {
  month.value = "";
  day.value = "";
});
watch(month, () => (day.value = ""));
watch([year, month, day, source], () => {
  offset.value = 0;
  void reload();
});
watch(offset, reload);
void reload();
onBeforeUnmount(() => request?.abort());
</script>
<template>
  <div class="logs-page">
    <div class="page-heading">
      <h2>로그</h2>
      <button class="source-button" :disabled="loading" @click="reload">
        <RefreshCw :size="16" />새로고침
      </button>
    </div>
    <section
      class="panel control-section log-filters"
      aria-label="실험 기록 필터"
    >
      <label
        >연도<select v-model="year">
          <option value="">전체 연도</option>
          <option v-for="value in years" :key="value">{{ value }}</option>
        </select></label
      >
      <label
        >월<select v-model="month">
          <option value="">전체 월</option>
          <option v-for="value in months" :value="value" :key="value">
            {{ Number(value) }}월
          </option>
        </select></label
      >
      <label
        >일<select v-model="day">
          <option value="">전체 일</option>
          <option v-for="value in days" :value="value" :key="value">
            {{ Number(value) }}일
          </option>
        </select></label
      >
      <label
        >실행 대상<select v-model="source">
          <option value="">전체</option>
          <option value="real">실제 모터</option>
          <option value="mock">가상 모터</option>
        </select></label
      >
      <span class="subtle">{{ total.toLocaleString() }}개 실험</span>
    </section>
    <p v-if="error" class="control-error" role="alert">{{ error }}</p>
    <section class="panel">
      <div class="log-table-wrap">
        <table class="log-table" aria-label="실험 기록">
          <thead>
            <tr>
              <th>시작 시간</th>
              <th>모터</th>
              <th>조건</th>
              <th>진행 시간</th>
              <th>완료 왕복</th>
              <th>상태</th>
              <th>분석</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="run in runs" :key="run.runId">
              <td>
                {{ formatTime(run.startedAt)
                }}<small>{{
                  run.source === "mock" ? "가상 모터" : "실제 모터"
                }}</small>
              </td>
              <td>
                {{ run.motorModel }}<small>ID {{ run.motorId }}</small>
              </td>
              <td>{{ conditionLabel(run.condition) }}</td>
              <td>{{ (run.elapsedMs / 1000).toFixed(1) }}초</td>
              <td>{{ run.completedCycles }}회</td>
              <td>
                <span class="run-badge" :class="run.status">{{
                  statusLabel(run.status)
                }}</span>
              </td>
              <td>
                <RouterLink
                  v-if="terminal(run)"
                  :to="{ path: `/logs/${run.runId}`, query: $route.query }"
                  >기록 보기 →</RouterLink
                ><RouterLink
                  v-else
                  :to="{
                    path: '/trends',
                    query: { source: run.source === 'mock' ? 'mock' : 'csv' },
                  }"
                  >실시간 보기 →</RouterLink
                >
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="!runs.length" class="empty-runs">
        {{ loading ? "기록 불러오는 중" : "저장된 실험이 없습니다" }}
      </div>
      <div v-if="total > 30" class="log-pagination">
        <button
          class="source-button"
          :disabled="offset === 0 || loading"
          @click="offset -= 30"
        >
          이전</button
        ><span
          >{{ Math.floor(offset / 30) + 1 }} / {{ Math.ceil(total / 30) }}</span
        ><button
          class="source-button"
          :disabled="offset + 30 >= total || loading"
          @click="offset += 30"
        >
          다음
        </button>
      </div>
    </section>
  </div>
</template>
