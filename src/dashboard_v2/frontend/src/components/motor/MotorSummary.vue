<script setup lang="ts">
import { computed, defineAsyncComponent } from "vue";
import { useMotorSlot } from "../../services/motorSlot";
import { useOverview } from "../../composables/useOverview";
import { useShaftPosition } from "../../composables/useShaftPosition";
import { useControlStore } from "../../stores/controlStore";
import { diagnosisView, formatValue } from "../../services/overview";
import RunControls from "../control/RunControls.vue";
const MotorModel3D = defineAsyncComponent(() => import("./MotorModel3D.vue"));
const slot = useMotorSlot(),
  control = useControlStore();
const { store, latest, history, selectedMotor } = useOverview();
const context = computed(
  () => `${slot}:${store.mode}:${store.experiment?.runId}`,
);
const { origin } = useShaftPosition(history, context);
const diagnosis = computed(() => diagnosisView(latest.value));
const rows = computed(
  () =>
    [
      ["전류", latest.value?.current, "A", 3],
      ["속도", latest.value?.velocity, "rpm", 2],
      ["위치", latest.value?.position, "pulse", 0],
      ["출력 PWM", latest.value?.pwm, "%", 1],
      ["입력 전압", latest.value?.voltage, "V", 1],
      ["온도", latest.value?.temperature, "°C", 0],
    ] as const,
);
</script>
<template>
  <section class="panel motor-summary" :data-motor="slot">
    <div class="dual-page-heading">
      <h2>모터 {{ slot }}</h2>
      <strong class="summary-diagnosis" :class="diagnosis.state">{{
        diagnosis.label
      }}</strong>
    </div>
    <div v-if="store.connection !== 'connected'" class="subtle">연결 대기</div>
    <div v-else-if="store.system.validity === 'stale'" class="subtle">
      갱신 지연
    </div>
    <div class="summary-motor-visual">
      <MotorModel3D
        :position="latest?.position ?? null"
        :origin="origin"
        :context="context"
        :model="
          selectedMotor?.model ??
          String(control.state?.saved?.config.motor_name ?? 'XM430-W210')
        "
        :interval-ms="(store.experiment?.sampleIntervalSec ?? 0.1) * 1000"
      />
    </div>
    <div class="summary-movement">
      {{ latest ? (latest.moving ? "회전 중" : "멈춤") : "데이터 대기" }}
    </div>
    <RunControls :show-target="false" />
    <div class="summary-metrics">
      <div v-for="[name, value, unit, decimals] in rows" :key="name">
        <span>{{ name }}</span
        ><strong
          >{{ formatValue(value, decimals) }} <small>{{ unit }}</small></strong
        >
      </div>
    </div>
    <div class="summary-timing">
      <span
        >데이터 수집 주기
        {{ store.experiment?.sampleIntervalSec ?? "—" }}초</span
      ><span>화면 갱신 0.1초</span>
    </div>
    <RouterLink
      class="source-button summary-link"
      :to="{ path: '/', query: { motor: String(slot) } }"
      >모터 {{ slot }} 개요 보기 →</RouterLink
    >
  </section>
</template>
