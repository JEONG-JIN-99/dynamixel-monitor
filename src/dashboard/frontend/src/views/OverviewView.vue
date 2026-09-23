<script setup lang="ts">
import { computed } from "vue";
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
import motorImage from "../assets/motor-servo.png";
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
  {
    label: "현재 위치",
    value: latest.value?.position,
    unit: "pulse",
    decimals: 0,
  },
  {
    label: "현재 속도",
    value: latest.value?.velocity,
    unit: "rpm",
    decimals: 1,
  },
  {
    label: latest.value?.loadPercent != null ? "현재 부하" : "현재 전류",
    value: latest.value?.loadPercent ?? latest.value?.current,
    unit: latest.value?.loadPercent != null ? "%" : "A",
    decimals: latest.value?.loadPercent != null ? 1 : 3,
  },
  { label: "온도", value: latest.value?.temperature, unit: "°C", decimals: 0 },
  { label: "입력 전압", value: latest.value?.voltage, unit: "V", decimals: 1 },
  { label: "출력 PWM", value: latest.value?.pwm, unit: "%", decimals: 1 },
]);
const notice = computed(() => {
  if (store.mode === "mock")
    return store.connection === "connected"
      ? ""
      : "가상 데이터 서버 연결 대기 중입니다. 마지막 수신 구간을 표시합니다.";
  if (store.system.error) return store.system.error;
  if (store.connection !== "connected")
    return "데이터 서버 연결 대기 중입니다. 수신된 마지막 기록이 있으면 유지합니다.";
  if (!store.system.readerCaughtUp)
    return "저장된 데이터를 읽고 있습니다. 최근 60초 구간으로 이동합니다.";
  if (
    ["completed", "interrupted", "failed"].includes(
      store.system.experimentStatus,
    )
  )
    return "데이터 수집이 종료되었습니다. 마지막 측정 구간을 표시합니다.";
  if (store.system.validity === "stale")
    return "데이터 갱신이 지연되고 있습니다. 마지막 측정 구간을 표시합니다.";
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
          <img :src="motorImage" alt="모터 외형 참고 이미지" />
        </div>
        <div class="movement" :class="{ muted: !latest }">
          <component :is="latest?.moving ? RefreshCw : Pause" :size="20" />{{
            movement
          }}
        </div>
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
            <p>
              {{
                diagnosis.state === "waiting"
                  ? "알고리즘 결과를 기다리고 있습니다"
                  : store.mode === "mock"
                    ? "가상 데이터 · 판정 예시"
                    : "알고리즘 판정 · 마지막 측정 기준"
              }}
            </p>
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
        :run-id="store.experiment?.runId"
        :decimals="3"
        :fields="[{ key: 'current', label: '측정값', color: '#bd9aff' }]"
      />
      <TelemetryChart
        title="속도"
        unit="rpm"
        :samples="history"
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
  <div class="data-caption source-path">
    <span>{{
      store.mode === "mock"
        ? "가상 데이터 · 실제 모터와 연결되지 않음"
        : (store.experiment?.csvPath ??
          "CSV 연결 대기 · 실험 복사본 실행 후 자동 연결됩니다")
    }}</span
    ><span>수신 데이터 기준 표시</span>
  </div>
</template>
