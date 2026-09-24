<script setup lang="ts">
import { computed, ref, shallowRef, watch, onBeforeUnmount } from "vue";
import {
  Activity,
  Clock3,
  RefreshCw,
  Pause,
  Play,
  ChevronDown,
  CircleAlert,
} from "lucide-vue-next";
import { disconnect } from "echarts/core";
import FaultEpisodes from "../components/charts/FaultEpisodes.vue";
import { faultEpisodes, type FaultEpisode } from "../services/faultEpisodes";
import {
  elapsedTime,
  clockTime,
  timeOrigin,
  durationText,
  type TimeMode,
} from "../services/analysisTime";
import StatusHistoryBar from "../components/charts/StatusHistoryBar.vue";
import { useAnalysisHistory } from "../composables/useAnalysisHistory";
import TelemetryChart from "../components/charts/TelemetryChart.vue";
import { useOverview } from "../composables/useOverview";
import {
  motorKey,
  diagnosisView,
  SCREEN_INTERVAL_MS,
} from "../services/overview";
import {
  analysisHistory,
  plotHistory,
  timeSegments,
} from "../services/analysis";
import { supportedModels } from "../services/controlTable";
import type { AnalysisPoint, PlotField, PlotKey } from "../types/analysis";
import "../styles/trends.css";
import { useRoute } from "vue-router";
import { useRecordedRun } from "../composables/useRecordedRun";
import { statusLabel } from "../stores/controlStore";
const route = useRoute();
const recordId = computed(() => String(route.params.runId ?? ""));
const isReplay = computed(() => !!recordId.value);
const overview = useOverview();
const { store, history } = overview;
const options = computed(() =>
  isReplay.value
    ? replay.record.value
      ? [
          {
            model: replay.record.value.motorModel,
            id: replay.record.value.motorId,
          },
        ]
      : []
    : overview.options.value,
);
const selectedKey = computed({
  get: () =>
    isReplay.value
      ? options.value[0]
        ? motorKey(options.value[0])
        : ""
      : overview.selectedKey.value,
  set: (v: string) => {
    if (!isReplay.value) overview.selectedKey.value = v;
  },
});
const selectedMotor = computed(() =>
  options.value.find((m) => motorKey(m) === selectedKey.value),
);
const metadata = computed(() =>
  isReplay.value
    ? replay.metadata.value
    : store.metadata.find((m) => motorKey(m) === selectedKey.value),
);
const duration = ref(isReplay.value ? 0 : 60);
watch(recordId, () => {
  duration.value = isReplay.value ? 0 : 60;
});
const replay = useRecordedRun(recordId, duration);
const ranges = [
  { value: 60, label: "60초" },
  { value: 300, label: "5분" },
  { value: 600, label: "10분" },
  { value: 1800, label: "30분" },
  { value: 3600, label: "1시간" },
  { value: 0, label: "전체" },
];
const rangeLabel = computed(
  () => ranges.find((r) => r.value === duration.value)!.label,
);
const archive = useAnalysisHistory(
  selectedKey,
  duration,
  computed(() => !isReplay.value),
);
const livePoints = computed(() =>
  isReplay.value
    ? replay.points.value
    : duration.value === 60
      ? analysisHistory(history.value, metadata.value)
      : archive.points.value,
);
const statusSegments = computed(() =>
  timeSegments(points.value, "diagnosis", intervalMs.value),
);
const xRange = computed(() => {
  const end = (points.value.at(-1)?.elapsedMs ?? 0) / 1000;
  return {
    start: duration.value ? Math.max(0, end - duration.value) : 0,
    end: Math.max(duration.value === 60 ? 60 : 1, end),
  };
});
const paused = ref(false);
const frozen = shallowRef<AnalysisPoint[]>([]);
const frozenInterval = ref(100);
const frozenLive = ref(false);
const timeMode = ref<TimeMode>("elapsed");
const focusedRange = ref<{ start: number; end: number } | null>(null);
const chartGrid = ref<HTMLElement>();
const collectionInterval = computed(() => {
  if (isReplay.value)
    return replay.record.value
      ? replay.record.value.sampleIntervalSec * 1000
      : null;
  const seconds = store.system.configuredHz
    ? 1 / store.system.configuredHz
    : store.experiment?.sampleIntervalSec;
  return seconds && seconds > 0 ? seconds * 1000 : null;
});
const intervalMs = computed(() =>
  paused.value ? frozenInterval.value : (collectionInterval.value ?? 100),
);
const points = computed(() => (paused.value ? frozen.value : livePoints.value));
const origin = computed(() => timeOrigin(points.value));
const crossesDate = computed(
  () =>
    origin.value != null &&
    clockTime(origin.value + xRange.value.start * 1000, true).slice(0, 10) !==
      clockTime(origin.value + xRange.value.end * 1000, true).slice(0, 10),
);
const formatTime = computed(() => {
  const base = origin.value,
    mode = timeMode.value,
    withDate = crossesDate.value;
  return (seconds: number, precise = false) =>
    mode === "clock"
      ? clockTime(
          base == null ? null : base + seconds * 1000,
          withDate,
          precise,
        )
      : elapsedTime(seconds, precise);
});
const tooltipTime = computed(() => {
  const base = origin.value;
  return (seconds: number) =>
    `실험 경과 ${elapsedTime(seconds, true)} · 실제 시각 ${clockTime(base == null ? null : base + seconds * 1000, true, true)}`;
});
watch(origin, (base) => {
  if (base == null) timeMode.value = "elapsed";
});
const streamActive = computed(
  () =>
    !isReplay.value &&
    store.connection === "connected" &&
    store.system.validity === "valid" &&
    ["running", "finishing"].includes(store.system.experimentStatus),
);
const episodes = computed(() =>
  faultEpisodes(
    points.value,
    intervalMs.value,
    streamActive.value && (!paused.value || frozenLive.value),
  ),
);
const hasDiagnosis = computed(() =>
  points.value.some((p) => diagnosisView(p).state !== "waiting"),
);
function inspectEpisode(item: FaultEpisode) {
  if (!isReplay.value && !paused.value) togglePause();
  const start = item.startMs / 1000,
    end = (item.endMs ?? item.lastMs) / 1000;
  const padding = Math.max(
    (end - start) * 0.15,
    (intervalMs.value / 1000) * 2,
    0.1,
  );
  focusedRange.value = {
    start: Math.max(xRange.value.start, start - padding),
    end: Math.min(xRange.value.end, end + padding),
  };
  chartGrid.value?.scrollIntoView({ behavior: "smooth", block: "start" });
}
const plotted = computed(() => plotHistory(points.value, intervalMs.value));
const latest = computed(() => points.value.at(-1) ?? null);
const diagnosis = computed(() => diagnosisView(latest.value));
const span = computed(() =>
  points.value.length < 2
    ? 0
    : Math.min(
        duration.value || Infinity,
        (points.value.at(-1)!.elapsedMs - points.value[0]!.elapsedMs) / 1000,
      ),
);
const faults = computed(() =>
  timeSegments(points.value, "diagnosis", intervalMs.value).filter(
    (s) => s.tone === "fault",
  ),
);
const notice = computed(() => {
  if (isReplay.value)
    return replay.loading.value ? "기록 불러오는 중" : replay.error.value;
  if (archive.loading.value) return "기록 불러오는 중";
  if (archive.error.value) return archive.error.value;
  if (
    selectedMotor.value &&
    !supportedModels.includes(selectedMotor.value.model)
  )
    return "지원하지 않는 모터입니다.";
  if (paused.value) return "화면 일시정지";
  if (store.connection !== "connected") return "연결 대기 · 마지막 수신값 표시";
  if (
    store.system.validity === "stale" ||
    store.system.validity === "error" ||
    ["completed", "interrupted", "failed"].includes(
      store.system.experimentStatus,
    )
  )
    return "수신 중단 또는 지연 · 마지막 수신값 표시";
  return "";
});
function togglePause() {
  if (!paused.value) {
    frozen.value = points.value;
    frozenInterval.value = intervalMs.value;
    frozenLive.value = streamActive.value;
  }
  paused.value = !paused.value;
  if (!paused.value) focusedRange.value = null;
}
watch(
  () => [
    recordId.value,
    selectedKey.value,
    isReplay.value ? null : store.mode,
    isReplay.value ? null : store.experiment?.runId,
    duration.value,
  ],
  () => {
    paused.value = false;
    frozen.value = [];
    focusedRange.value = null;
  },
  { flush: "sync" },
);
const group = "motor-detailed-analysis";
onBeforeUnmount(() => disconnect(group));
const showLimits = ref(false);
interface ChartDefinition {
  title: string;
  unit: string;
  decimals: number;
  key: PlotKey;
  fields: PlotField[];
  derived?: boolean;
}
const charts: ChartDefinition[] = [
  {
    title: "전류",
    key: "current",
    unit: "A",
    decimals: 3,
    fields: [{ key: "current", label: "측정 전류", color: "#bd9aff" }],
  },
  {
    title: "속도",
    key: "velocity",
    unit: "rpm",
    decimals: 2,
    fields: [
      { key: "velocity", label: "측정 속도", color: "#59d6b2" },
      {
        key: "velocityTrajectory",
        label: "목표 궤적",
        color: "#f2bd72",
        dashed: true,
      },
    ],
  },
  {
    title: "위치",
    key: "position",
    unit: "pulse",
    decimals: 0,
    fields: [
      { key: "position", label: "측정 위치", color: "#70aaff" },
      {
        key: "positionTrajectory",
        label: "목표 궤적",
        color: "#f2bd72",
        dashed: true,
      },
      {
        key: "goalPosition",
        label: "명령 목표",
        color: "#ef91bc",
        dotted: true,
        dashed: true,
      },
    ],
  },
  {
    title: "PWM",
    key: "pwm",
    unit: "%",
    decimals: 1,
    fields: [{ key: "pwm", label: "현재 PWM", color: "#f2bd72" }],
  },
  {
    title: "입력 전압",
    key: "voltage",
    unit: "V",
    decimals: 1,
    fields: [{ key: "voltage", label: "측정 전압", color: "#66ccec" }],
  },
  {
    title: "내부 온도",
    key: "temperature",
    unit: "°C",
    decimals: 0,
    fields: [{ key: "temperature", label: "측정 온도", color: "#ef9b87" }],
  },
  {
    title: "위치 추종 오차",
    key: "positionError",
    unit: "pulse",
    decimals: 0,
    derived: true,
    fields: [
      {
        key: "positionError",
        label: "실제 위치 − 목표 궤적",
        color: "#8db5ff",
      },
    ],
  },
  {
    title: "속도 추종 오차",
    key: "velocityError",
    unit: "rpm",
    decimals: 3,
    derived: true,
    fields: [
      {
        key: "velocityError",
        label: "실제 속도 − 목표 궤적",
        color: "#76dbc2",
      },
    ],
  },
];
</script>
<template>
  <div
    class="trends-page"
    :data-sample-count="points.length"
    :data-last-elapsed="latest?.elapsedMs"
  >
    <div class="trends-heading">
      <div class="analysis-title-controls">
        <div class="record-heading">
          <RouterLink
            v-if="isReplay"
            :to="{ path: '/logs', query: $route.query }"
            class="record-link"
            >← 로그</RouterLink
          >
          <h2>{{ isReplay ? "실험 기록" : "상세 분석" }}</h2>
        </div>
        <select
          v-model.number="duration"
          aria-label="분석 시간 범위"
          class="analysis-range"
        >
          <option
            v-for="range in ranges"
            :key="range.value"
            :value="range.value"
          >
            {{ range.label }}
          </option>
        </select>
      </div>
      <div class="trends-actions">
        <div class="time-mode-switch" role="group" aria-label="시간 표시 기준">
          <button
            :aria-pressed="timeMode === 'elapsed'"
            @click="timeMode = 'elapsed'"
          >
            실험 경과
          </button>
          <button
            :aria-pressed="timeMode === 'clock'"
            :disabled="origin == null"
            @click="timeMode = 'clock'"
          >
            실제 시각
          </button>
        </div>
        <div class="select-wrap">
          <select
            v-model="selectedKey"
            aria-label="분석할 모터"
            :disabled="!options.length"
          >
            <option v-if="!options.length" value="">수신된 모터 없음</option>
            <option
              v-for="motor in options"
              :key="motorKey(motor)"
              :value="motorKey(motor)"
            >
              {{ motor.model }} · ID {{ motor.id }}
            </option></select
          ><ChevronDown :size="18" />
        </div>
        <button
          v-if="!isReplay"
          class="source-button"
          :aria-pressed="paused"
          @click="togglePause"
        >
          <component :is="paused ? Play : Pause" :size="15" />{{
            paused ? "화면 재개" : "화면 일시정지"
          }}
        </button>
      </div>
    </div>
    <div v-if="notice" class="notice" role="status">
      <CircleAlert :size="16" />{{ notice }}
      <button
        v-if="archive.error.value || replay.error.value"
        class="source-button"
        @click="isReplay ? replay.reload() : archive.reload()"
      >
        다시 시도
      </button>
    </div>
    <section class="panel timing-bar" aria-label="분석 표시 주기">
      <div>
        <Activity :size="18" /><span
          >데이터 수집 주기
          <strong>{{
            collectionInterval ? `${collectionInterval / 1000}초` : "미수신"
          }}</strong></span
        >
      </div>
      <div>
        <Clock3 :size="18" /><span
          >{{ duration ? "최근" : "실험 구간" }}
          <strong>{{ rangeLabel }}</strong></span
        >
      </div>
      <div v-if="!isReplay">
        <RefreshCw :size="18" /><span
          >화면 갱신 <strong>{{ SCREEN_INTERVAL_MS / 1000 }}초</strong></span
        >
      </div>
      <div v-if="isReplay && replay.record.value" class="subtle">
        {{
          new Date(replay.record.value.startedAt).toLocaleString("ko-KR", {
            timeZone: "Asia/Seoul",
          })
        }}
        · {{ statusLabel(replay.record.value.status) }}
      </div>
      <div class="trends-buffer">표시 구간 {{ durationText(span * 1000) }}</div>
    </section>
    <section
      v-if="!isReplay"
      class="panel analysis-summary"
      aria-label="분석 상태"
    >
      <div
        class="analysis-verdict"
        :class="diagnosis.state"
        role="status"
        aria-label="알고리즘 판정 결과"
      >
        <strong>{{ diagnosis.label }}</strong>
      </div>
    </section>
    <div class="trends-section-title">
      <h3>측정값</h3>
      <div class="measurement-tools">
        <span class="zoom-hint">그래프 확대: <kbd>Ctrl</kbd> + 마우스 휠</span>
        <label class="limit-toggle">
          <input v-model="showLimits" type="checkbox" />설정 한계선 표시
        </label>
      </div>
    </div>
    <div ref="chartGrid" class="trends-chart-grid">
      <TelemetryChart
        v-for="chart in charts.filter((c) => !c.derived)"
        :key="chart.key"
        :title="chart.title"
        :unit="chart.unit"
        :decimals="chart.decimals"
        :fields="chart.fields"
        :samples="plotted"
        :group="group"
        :run-id="`${recordId || store.experiment?.runId}:${selectedKey}:${duration}`"
        :time-range="xRange"
        :format-time="formatTime"
        :tooltip-time="tooltipTime"
        :focus-range="focusedRange"
        @inspect="!isReplay && !paused && togglePause()"
        :fault-segments="faults"
        :reference-lines="showLimits ? latest?.limits[chart.key] : []"
      />
    </div>
    <div class="trends-section-title">
      <h3>추종 오차</h3>
    </div>
    <div class="trends-chart-grid">
      <TelemetryChart
        v-for="chart in charts.filter((c) => c.derived)"
        :key="chart.key"
        :title="chart.title"
        :unit="chart.unit"
        :decimals="chart.decimals"
        :fields="chart.fields"
        :samples="plotted"
        :group="group"
        :run-id="`${recordId || store.experiment?.runId}:${selectedKey}:${duration}`"
        :time-range="xRange"
        :format-time="formatTime"
        :tooltip-time="tooltipTime"
        :focus-range="focusedRange"
        @inspect="!isReplay && !paused && togglePause()"
        :fault-segments="faults"
        zero-centered
        empty-text="표시할 데이터가 없습니다"
      />
    </div>
    <StatusHistoryBar
      :segments="statusSegments"
      :time-range="xRange"
      :format-time="formatTime"
      :tooltip-time="tooltipTime"
    />
    <FaultEpisodes
      :episodes="episodes"
      :has-diagnosis="hasDiagnosis"
      :format-time="formatTime"
      :tooltip-time="tooltipTime"
      :context="`${recordId || store.experiment?.runId}:${selectedKey}:${duration}`"
      @inspect="inspectEpisode"
    />
  </div>
</template>
