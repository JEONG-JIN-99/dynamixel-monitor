<script setup lang="ts">
import { elapsedTime } from "../../services/analysisTime";
import { computed } from "vue";
import type { TimeSegment } from "../../types/analysis";
const props = defineProps<{
  segments: TimeSegment[];
  formatTime?: (seconds: number, precise?: boolean) => string;
  tooltipTime?: (seconds: number) => string;
  timeRange: { start: number; end: number };
}>();
const width = computed(() =>
  Math.max(0.1, props.timeRange.end - props.timeRange.start),
);
const visible = computed(() =>
  props.segments.filter(
    (s) => s.end > props.timeRange.start && s.start < props.timeRange.end,
  ),
);
function label(s: TimeSegment) {
  return s.tone === "fault" ? "이상" : s.tone === "active" ? "정상" : "미수신";
}
function percent(t: number) {
  return Math.max(
    0,
    Math.min(100, ((t - props.timeRange.start) / width.value) * 100),
  );
}
function time(t: number) {
  return props.formatTime ? props.formatTime(t, true) : elapsedTime(t, true);
}
</script>
<template>
  <section class="panel status-history" aria-label="상태 이력">
    <div class="status-history-heading">
      <h3>상태 이력</h3>
      <div class="status-history-legend">
        <span><i class="normal"></i>정상</span
        ><span><i class="fault"></i>이상</span>
      </div>
    </div>
    <div
      class="status-history-track"
      role="img"
      aria-label="시간별 정상 및 이상 구간"
    >
      <span
        v-for="(segment, index) in visible"
        :key="index"
        class="status-history-segment"
        :class="{
          normal: segment.tone === 'active',
          fault: segment.tone === 'fault',
        }"
        :style="{
          left: `${percent(segment.start)}%`,
          width: `${percent(segment.end) - percent(segment.start)}%`,
        }"
        :title="`${segment.label || label(segment)} · ${props.tooltipTime?.(segment.start) ?? time(segment.start)} → ${props.tooltipTime?.(segment.end) ?? time(segment.end)}`"
      ></span>
      <span v-if="!visible.length" class="status-history-empty"
        >표시할 데이터가 없습니다</span
      >
    </div>
    <div class="status-history-axis">
      <span>{{ time(timeRange.start) }}</span
      ><span>{{ time((timeRange.start + timeRange.end) / 2) }}</span
      ><span>{{ time(timeRange.end) }}</span>
    </div>
  </section>
</template>
