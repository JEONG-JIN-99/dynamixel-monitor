<script setup lang="ts">
import { computed, defineAsyncComponent } from "vue";
import {
  Activity,
  Clock3,
  RefreshCw,
  CircleCheck,
  CircleAlert,
  CircleDashed,
  ChevronDown,
  Pause,
} from "lucide-vue-next";
import TelemetryChart from "../components/charts/TelemetryChart.vue";
import RunControls from "../components/control/RunControls.vue";
import { useShaftPosition } from "../composables/useShaftPosition";
import { elapsedTime } from "../services/analysisTime";
const formatTooltipTime = (seconds: number) => elapsedTime(seconds, true);
const MotorModel3D = defineAsyncComponent(
  () => import("../components/motor/MotorModel3D.vue"),
);
import { useOverview } from "../composables/useOverview";
import {
  diagnosisLabels,
  diagnosisView,
  formatValue,
  motorKey,
  SCREEN_INTERVAL_MS,
} from "../services/overview";
const { store, options, selectedKey, selectedMotor, history, latest } =
  useOverview();
const shaftContext = computed(() =>
  JSON.stringify([
    store.mode,
    store.serverSession,
    store.sourceSession,
    store.experiment?.runId,
    selectedKey.value,
  ]),
);
const { origin } = useShaftPosition(history, shaftContext);
const diagnosis = computed(() => diagnosisView(latest.value));
const interval = computed(() => {
  const seconds =
    store.experiment?.sampleIntervalSec ??
    (store.system.configuredHz ? 1 / store.system.configuredHz : null);
  return seconds && seconds > 0 ? `${Number(seconds.toFixed(4))}초` : "—";
});
const movement = computed(() => {
  if (!latest.value) return "데이터 대기";
  if (latest.value.moving == null) return "이동 상태 미수신";
  if (store.mode === "csv" && !store.live)
    return "마지막 기록 · " + (latest.value.moving ? "회전 중" : "멈춤");
  return latest.value.moving ? "회전 중" : "멈춤";
});
const metrics = computed(() => [
  { label: "온도", value: latest.value?.temperature, unit: "°C", decimals: 0 },
  { label: "입력 전압", value: latest.value?.voltage, unit: "V", decimals: 1 },
  { label: "출력 PWM", value: latest.value?.pwm, unit: "%", decimals: 1 },
]);
const notice = computed(() => {
  if (store.connection !== "connected") return "연결 대기";
  if (store.system.error) return "데이터 오류";
  if (!store.system.readerCaughtUp) return "데이터 불러오는 중";
  if (store.system.validity === "stale") return "갱신 지연";
  return "";
});
</script>
<template>
  <div v-if="notice" class="notice" role="status">
    <CircleAlert :size="16" />{{ notice }}
  </div>
  <div class="overview-grid">
    <div class="motor-column">
      <section class="panel motor-card" aria-labelledby="motor-label">
        <h2 id="motor-label">모터종류</h2>
        <div class="motor-picker">
          <div class="select-wrap">
            <select
              v-model="selectedKey"
              aria-label="모터종류"
              :disabled="!options.length"
            >
              <option v-if="!options.length" value="">수신된 모터 없음</option>
              <option
                v-for="motor in options"
                :key="motorKey(motor)"
                :value="motorKey(motor)"
              >
                {{ motor.model
                }}{{
                  options.filter((m) => m.model === motor.model).length > 1
                    ? ` · ID ${motor.id}`
                    : ""
                }}
              </option></select
            ><ChevronDown :size="20" />
          </div>
          <span class="motor-id">ID {{ selectedMotor?.id ?? "—" }}</span>
        </div>
        <div class="motor-visual">
          <MotorModel3D
            :position="latest?.position ?? null"
            :origin="origin"
            :context="shaftContext"
            :model="selectedMotor?.model ?? 'XM430-W210'"
            :interval-ms="(store.experiment?.sampleIntervalSec ?? 0.1) * 1000"
          />
          <div class="movement" :class="{ muted: !latest }">
            <component :is="latest?.moving ? RefreshCw : Pause" :size="20" />{{
              movement
            }}
          </div>
        </div>
        <RunControls :show-target="false" />
        <div class="metric-grid">
          <div
            v-for="metric in metrics"
            :key="metric.label"
            class="metric-card"
          >
            <span class="metric-label">{{ metric.label }}</span>
            <div class="metric-value">
              {{ formatValue(metric.value, metric.decimals)
              }}<small>{{ metric.unit }}</small>
            </div>
          </div>
        </div>
      </section>
      <section class="panel diagnosis-card" aria-labelledby="diagnosis-heading">
        <h2 id="diagnosis-heading">이상 진단 결과</h2>
        <div class="diagnosis-result" :class="diagnosis.state" role="status">
          <div class="diagnosis-icon">
            <component
              :is="
                diagnosis.state === 'normal'
                  ? CircleCheck
                  : diagnosis.state === 'fault'
                    ? CircleAlert
                    : CircleDashed
              "
              :size="38"
            />
          </div>
          <div>
            <strong>{{ diagnosis.label }}</strong>
          </div>
        </div>
        <div class="diagnosis-categories">
          <span>진단 항목</span>
          <div>
            <span
              v-for="(label, code) in diagnosisLabels"
              :key="code"
              class="diagnosis-chip"
              :class="{ detected: diagnosis.codes.includes(code) }"
              >{{ label }}</span
            >
          </div>
        </div>
      </section>
    </div>
    <div class="charts-column">
      <section
        class="panel timing-bar"
        aria-label="데이터 수집 및 화면 표시 주기"
      >
        <div>
          <Activity :size="21" /><span
            >데이터 수집 주기 <strong>{{ interval }}</strong></span
          >
        </div>
        <div>
          <Clock3 :size="21" /><span
            >최근 <strong>{{ store.retentionSec }}초</strong></span
          >
        </div>
        <div>
          <RefreshCw :size="20" /><span
            >화면 갱신 <strong>{{ SCREEN_INTERVAL_MS / 1000 }}초</strong></span
          >
        </div>
      </section>
      <TelemetryChart
        title="전류"
        unit="A"
        :samples="history"
        :format-time="elapsedTime"
        :tooltip-time="formatTooltipTime"
        :run-id="store.experiment?.runId"
        :decimals="3"
        :fields="[{ key: 'current', label: '측정값', color: '#bd9aff' }]"
      />
      <TelemetryChart
        title="속도"
        unit="rpm"
        :samples="history"
        :format-time="elapsedTime"
        :tooltip-time="formatTooltipTime"
        :run-id="store.experiment?.runId"
        :decimals="1"
        :fields="[
          { key: 'velocity', label: '측정값', color: '#59d6b2' },
          {
            key: 'velocityTrajectory',
            label: '궤적',
            color: '#f2bd72',
            dashed: true,
          },
        ]"
      />
      <TelemetryChart
        title="위치"
        unit="pulse"
        :samples="history"
        :format-time="elapsedTime"
        :tooltip-time="formatTooltipTime"
        :run-id="store.experiment?.runId"
        :decimals="0"
        :fields="[
          { key: 'position', label: '측정값', color: '#70aaff' },
          {
            key: 'positionTrajectory',
            label: '궤적',
            color: '#f2bd72',
            dashed: true,
          },
          {
            key: 'goalPosition',
            label: '목표값',
            color: '#ef91bc',
            dashed: true,
            dotted: true,
          },
        ]"
      />
    </div>
  </div>
</template>

<style scoped>
.motor-card {
  --card-inset: 18px;
  padding-inline: var(--card-inset);
  padding-bottom: 0;
}
.metric-grid {
  margin-inline: calc(-1 * var(--card-inset));
  border-inline: 0;
  border-bottom: 0;
  border-radius: 0;
}
@media (min-width: 1800px) {
  .motor-card {
    --card-inset: 22px;
  }
}
@media (max-width: 640px) {
  .motor-card {
    --card-inset: 12px;
  }
}
.motor-visual {
  min-height: 150px;
}
.metric-card {
  border-bottom: 0;
}
.movement {
  position: absolute;
  right: 0;
  bottom: 0;
  margin-bottom: 0;
}
</style>
