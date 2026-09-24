<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { use } from "echarts/core";
import type { EChartsType } from "echarts/core";
import { init, connect } from "echarts/core";
import { LineChart } from "echarts/charts";
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  MarkLineComponent,
  MarkAreaComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { Maximize2, RotateCcw } from "lucide-vue-next";
import { formatValue } from "../../services/overview";
import type {
  PlotPoint,
  PlotKey,
  PlotField,
  ReferenceLine,
  TimeSegment,
} from "../../types/analysis";
use([
  LineChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  MarkLineComponent,
  MarkAreaComponent,
  CanvasRenderer,
]);
const props = defineProps<{
  samples: PlotPoint[];
  timeRange?: { start: number; end: number };
  formatTime?: (seconds: number, precise?: boolean) => string;
  tooltipTime?: (seconds: number) => string;
  focusRange?: { start: number; end: number } | null;
  group?: string;
  zeroCentered?: boolean;
  referenceLines?: ReferenceLine[];
  faultSegments?: TimeSegment[];
  emptyText?: string;
  runId?: string;
  decimals?: number;
  title: string;
  unit: string;
  fields: PlotField[];
  wide?: boolean;
}>();
const emit = defineEmits<{ inspect: [] }>();
const latest = computed(() => props.samples.at(-1) ?? null);
const currentValue = computed(() => latest.value?.[props.fields[0]!.key]);
const element = ref<HTMLDivElement>();
let chart: EChartsType | undefined;
let observer: ResizeObserver | undefined;
const expanded = ref(false);
const hiddenFields = ref(new Set<PlotKey>());
const visibleFields = computed(() =>
  props.fields.filter((field) => !hiddenFields.value.has(field.key)),
);
function toggleField(key: PlotKey) {
  const hidden = new Set(hiddenFields.value);
  if (hidden.has(key)) hidden.delete(key);
  else {
    if (visibleFields.value.length === 1) return;
    hidden.add(key);
  }
  hiddenFields.value = hidden;
}
const empty = computed(
  () =>
    !props.samples.length ||
    visibleFields.value.every((f) =>
      props.samples.every((row) => row[f.key] == null),
    ),
);
const id = computed(() => props.title.toLowerCase().replaceAll(" ", "-"));
// Include reference lines with padding so both the stroke and label stay inside the plot.
function referenceBounds(extent: { min: number; max: number }) {
  const values = [
    extent.min,
    extent.max,
    ...(props.referenceLines ?? []).map((line) => line.value),
  ].filter(Number.isFinite);
  const low = Math.min(...values),
    high = Math.max(...values);
  const padding = Math.max(high - low, Math.abs(high) * 0.1, 0.1) * 0.1;
  return { min: low - padding, max: high + padding };
}
function render() {
  if (!chart) return;
  const last = (latest.value?.elapsedMs ?? 0) / 1000;
  chart.setOption({
    animation: false,
    backgroundColor: "transparent",
    textStyle: { fontFamily: "Segoe UI, Malgun Gothic, sans-serif" },
    grid: { left: 54, right: 20, top: 12, bottom: 32 },
    legend: {
      show: false,
      data: props.fields.map((field) => field.label),
      selected: Object.fromEntries(
        props.fields.map((field) => [
          field.label,
          !hiddenFields.value.has(field.key),
        ]),
      ),
    },
    tooltip: {
      trigger: "axis",
      className: "telemetry-tooltip",
      backgroundColor: "#182334",
      borderColor: "#34465e",
      textStyle: { color: "#e4edf9", fontSize: 11 },
      confine: true,
      valueFormatter: (v: unknown) =>
        typeof v === "number" ? v.toFixed(3) : String(v),
    },
    xAxis: {
      type: "value",
      min: props.timeRange?.start ?? Math.max(0, last - 60),
      max: props.timeRange?.end ?? Math.max(60, last),
      axisPointer: {
        label: {
          formatter: (params: { value: number }) =>
            props.tooltipTime?.(Number(params.value)) ?? String(params.value),
        },
      },
      axisLine: { lineStyle: { color: "#3a4b62" } },
      axisTick: { show: false },
      axisLabel: {
        color: "#9baec8",
        fontSize: 10,
        formatter: (v: number) =>
          props.formatTime
            ? props.formatTime(v, true)
            : `${Number(v.toFixed(3))}초`,
        hideOverlap: true,
      },
      splitLine: { show: false },
    },
    yAxis: {
      type: "value",
      scale: !props.zeroCentered,
      min: props.zeroCentered
        ? (extent: { min: number; max: number }) =>
            -Math.max(Math.abs(extent.min), Math.abs(extent.max), 1)
        : props.referenceLines?.some((line) => Number.isFinite(line.value))
          ? (extent: { min: number; max: number }) =>
              referenceBounds(extent).min
          : null,
      max: props.zeroCentered
        ? (extent: { min: number; max: number }) =>
            Math.max(Math.abs(extent.min), Math.abs(extent.max), 1)
        : props.referenceLines?.some((line) => Number.isFinite(line.value))
          ? (extent: { min: number; max: number }) =>
              referenceBounds(extent).max
          : null,
      splitNumber: 3,
      axisLabel: { color: "#9baec8", fontSize: 10 },
      splitLine: { lineStyle: { color: "#29384b", type: "dashed" } },
    },
    dataZoom: [
      {
        type: "inside",
        filterMode: "none",
        zoomOnMouseWheel: "ctrl",
        moveOnMouseMove: true,
      },
    ],
    series: props.fields.map((field, index) => ({
      markLine:
        index === 0
          ? {
              silent: true,
              symbol: "none",
              lineStyle: { color: "#8395af", type: "dashed", width: 1 },
              label: {
                position: "insideEndTop",
                color: "#a8b9d0",
                fontSize: 10,
                formatter: "{b}",
              },
              data: [
                ...(props.zeroCentered ? [{ value: 0, label: "기준 0" }] : []),
                ...(props.referenceLines ?? []),
              ].map((l) => ({
                yAxis: l.value,
                name: `${l.label} · ${l.value.toFixed(2)}`,
              })),
            }
          : undefined,
      markArea:
        index === 0
          ? {
              silent: true,
              itemStyle: { color: "rgba(255, 125, 151, 0.09)" },
              data: (props.faultSegments ?? []).map((s) => [
                { xAxis: s.start },
                { xAxis: s.end },
              ]),
            }
          : undefined,
      id: field.key,
      name: field.label,
      type: "line",
      // A narrow dashed reference leaves the wider measured line visible beneath it.
      z: field.dashed ? 4 : 3,
      showSymbol: false,
      connectNulls: false,
      step: field.key === "goalPosition" ? "end" : false,
      lineStyle: {
        color: field.color,
        width: props.fields.length === 1 ? 1.8 : field.dashed ? 1.4 : 3.4,
        type: field.dotted ? "dotted" : field.dashed ? "dashed" : "solid",
      },
      itemStyle: { color: field.color },
      areaStyle:
        props.fields.length === 1
          ? { color: field.color, opacity: 0.055 }
          : undefined,
      data: props.samples.map((sample) => [
        sample.elapsedMs / 1000,
        sample[field.key],
      ]),
    })),
  });
}
function resetZoom() {
  chart?.dispatchAction({ type: "dataZoom", start: 0, end: 100 });
}
onMounted(() => {
  chart = init(element.value!);
  chart.on("datazoom", (event: any) => {
    const zoom = event.batch?.[0] ?? event;
    if ((zoom.start ?? 0) > 0 || (zoom.end ?? 100) < 100) emit("inspect");
  });
  if (props.group) {
    chart.group = props.group;
    connect(props.group);
  }
  observer = new ResizeObserver(() => chart?.resize());
  observer.observe(element.value!);
  render();
});
watch(
  () => [
    props.samples,
    props.timeRange,
    props.referenceLines,
    props.faultSegments,
    props.formatTime,
    props.tooltipTime,
  ],
  render,
);
watch(hiddenFields, render);
watch(() => props.runId, resetZoom);
watch(
  () => props.focusRange,
  (range) => {
    if (range)
      chart?.dispatchAction({
        type: "dataZoom",
        startValue: range.start,
        endValue: range.end,
      });
    else resetZoom();
  },
  { flush: "post" },
);

function onKeydown(event: KeyboardEvent) {
  if (event.key === "Escape") expanded.value = false;
}
onMounted(() => window.addEventListener("keydown", onKeydown));
onBeforeUnmount(() => {
  window.removeEventListener("keydown", onKeydown);
  observer?.disconnect();
  chart?.dispose();
});
</script>
<template>
  <section class="panel chart-card" :class="{ wide, expanded }">
    <div class="panel-title">
      <div class="chart-heading">
        <h2 :id="id">{{ title }}</h2>
        <span class="chart-current"
          >현재값
          <strong>{{ formatValue(currentValue, decimals ?? 1) }}</strong>
          {{ unit }}</span
        >
      </div>
      <div class="chart-tools">
        <button @click="resetZoom" aria-label="차트 확대 초기화">
          <RotateCcw :size="12" /></button
        ><button
          @click="expanded = !expanded"
          :aria-label="expanded ? '차트 축소' : '차트 확대'"
        >
          <Maximize2 :size="13" />
        </button>
      </div>
    </div>
    <div class="chart-legend">
      <button
        v-for="field in fields"
        :key="field.key"
        type="button"
        class="legend-toggle"
        :class="{ hidden: hiddenFields.has(field.key) }"
        :aria-pressed="!hiddenFields.has(field.key)"
        :aria-label="field.label"
        :disabled="visibleFields.length === 1 && !hiddenFields.has(field.key)"
        :title="
          hiddenFields.has(field.key)
            ? '클릭하여 표시'
            : visibleFields.length === 1
              ? '최소 한 개의 선은 표시합니다'
              : '클릭하여 숨기기'
        "
        @click="toggleField(field.key)"
      >
        <i
          :class="{ dashed: field.dashed, dotted: field.dotted }"
          :style="{ borderColor: field.color }"
        ></i>
        {{ field.label }}
      </button>
      <span v-if="faultSegments !== undefined" class="chart-fault-legend">
        <i aria-hidden="true"></i>붉은 음영: 이상 구간
      </span>
    </div>
    <div class="chart-wrap">
      <div ref="element" class="chart" role="img" :aria-labelledby="id"></div>
      <div v-if="empty" class="empty-chart">
        {{
          props.emptyText ??
          (latest
            ? "해당 항목의 수신값이 없습니다"
            : "측정 데이터를 기다리고 있습니다")
        }}
      </div>
    </div>
  </section>
</template>
