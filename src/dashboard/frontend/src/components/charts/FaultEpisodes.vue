<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type { FaultEpisode } from "../../services/faultEpisodes";
import { durationText } from "../../services/analysisTime";
const props = defineProps<{
  episodes: FaultEpisode[];
  formatTime: (seconds: number, precise?: boolean) => string;
  tooltipTime: (seconds: number) => string;
  context: string;
  hasDiagnosis: boolean;
}>();
const emit = defineEmits<{ inspect: [episode: FaultEpisode] }>();
const page = ref(0),
  size = 20;
const pages = computed(() =>
  Math.max(1, Math.ceil(props.episodes.length / size)),
);
const visible = computed(() =>
  props.episodes.slice(page.value * size, (page.value + 1) * size),
);
watch(
  () => props.context,
  () => (page.value = 0),
);
watch(pages, (value) => (page.value = Math.min(page.value, value - 1)));
function start(item: FaultEpisode) {
  return item.leftBoundary === "window"
    ? "조회 구간 이전부터"
    : item.leftBoundary === "gap"
      ? "시작 미확인"
      : props.formatTime(item.startMs / 1000, true);
}
function end(item: FaultEpisode) {
  return item.endMs != null
    ? props.formatTime(item.endMs / 1000, true)
    : item.ending === "ongoing"
      ? "진행 중"
      : "종료 미확인";
}
</script>
<template>
  <section class="panel fault-episodes" aria-label="이상 발생 내역">
    <div class="status-history-heading">
      <h3>이상 발생 내역</h3>
      <span class="subtle">최근 발생순 · {{ episodes.length }}건</span>
    </div>
    <div class="fault-table-wrap">
      <table class="fault-table">
        <thead>
          <tr>
            <th>문제</th>
            <th>시작</th>
            <th>종료</th>
            <th>지속 시간</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="item in visible"
            :key="item.id"
            tabindex="0"
            role="button"
            :aria-label="`${item.label} ${start(item)} 구간 보기`"
            @click="emit('inspect', item)"
            @keydown.enter.prevent="emit('inspect', item)"
            @keydown.space.prevent="emit('inspect', item)"
          >
            <td>
              <span class="fault-name">{{ item.label }}</span>
            </td>
            <td :title="tooltipTime(item.startMs / 1000)">
              {{ start(item)
              }}<small v-if="item.leftBoundary !== 'known'"
                >{{ formatTime(item.startMs / 1000, true) }}부터 확인</small
              >
            </td>
            <td :title="tooltipTime((item.endMs ?? item.lastMs) / 1000)">
              {{ end(item)
              }}<small v-if="item.ending === 'unconfirmed'"
                >마지막 확인 {{ formatTime(item.lastMs / 1000, true) }}</small
              >
            </td>
            <td>
              {{ durationText((item.endMs ?? item.lastMs) - item.startMs)
              }}{{
                item.leftBoundary !== "known" || item.ending !== "resolved"
                  ? " 이상"
                  : ""
              }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <p v-if="!episodes.length" class="fault-empty">
      {{
        hasDiagnosis ? "이상 발생 내역이 없습니다" : "판정 데이터가 없습니다"
      }}
    </p>
    <div v-if="pages > 1" class="log-pagination">
      <button class="source-button" :disabled="page === 0" @click="page--">
        이전</button
      ><span>{{ page + 1 }} / {{ pages }}</span
      ><button
        class="source-button"
        :disabled="page + 1 >= pages"
        @click="page++"
      >
        다음
      </button>
    </div>
  </section>
</template>
