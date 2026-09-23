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
const { store, options, selectedKey, selectedMotor, history } = useOverview();
const metadata = computed(() =>
  store.metadata.find((m) => motorKey(m) === selectedKey.value),
);
const livePoints = computed(() =>
  analysisHistory(history.value, metadata.value),
);
const paused = ref(false);
const frozen = shallowRef<AnalysisPoint[]>([]);
const frozenInterval = ref(100);
const collectionInterval = computed(() => {
  const seconds = store.system.configuredHz
    ? 1 / store.system.configuredHz
    : store.experiment?.sampleIntervalSec;
  return seconds && seconds > 0 ? seconds * 1000 : null;
});
const intervalMs = computed(() =>
  paused.value ? frozenInterval.value : (collectionInterval.value ?? 100),
);
const points = computed(() => (paused.value ? frozen.value : livePoints.value));
const plotted = computed(() => plotHistory(points.value, intervalMs.value));
const latest = computed(() => points.value.at(-1) ?? null);
const diagnosis = computed(() => diagnosisView(latest.value));
const span = computed(() =>
  points.value.length < 2
    ? 0
    : Math.min(
        60,
        (points.value.at(-1)!.elapsedMs - points.value[0]!.elapsedMs) / 1000,
      ),
);
const faults = computed(() =>
  timeSegments(points.value, "diagnosis", intervalMs.value).filter(
    (s) => s.tone === "fault",
  ),
);
const notice = computed(() => {
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
  }
  paused.value = !paused.value;
}
watch(
  () => [selectedKey.value, store.mode, store.experiment?.runId],
  () => {
    paused.value = false;
    frozen.value = [];
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
  <div class="trends-page">
    <div class="trends-heading">
      <div>
        <h2>상세 분석</h2>
      </div>
      <div class="trends-actions">
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
        <Clock3 :size="18" /><span>최근 <strong>60초</strong></span>
      </div>
      <div>
        <RefreshCw :size="18" /><span
          >화면 갱신 <strong>{{ SCREEN_INTERVAL_MS / 1000 }}초</strong></span
        >
      </div>
      <div class="trends-buffer">수신 구간 {{ span.toFixed(1) }} / 60초</div>
    </section>
    <section class="panel analysis-summary" aria-label="분석 상태">
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
    <div class="trends-chart-grid">
      <TelemetryChart
        v-for="chart in charts.filter((c) => !c.derived)"
        :key="chart.key"
        :title="chart.title"
        :unit="chart.unit"
        :decimals="chart.decimals"
        :fields="chart.fields"
        :samples="plotted"
        :group="group"
        :run-id="`${store.experiment?.runId}:${selectedKey}`"
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
        :run-id="`${store.experiment?.runId}:${selectedKey}`"
        :fault-segments="faults"
        zero-centered
        empty-text="표시할 데이터가 없습니다"
      />
    </div>
  </div>
</template>
