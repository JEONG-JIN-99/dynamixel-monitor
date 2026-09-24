<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { Save } from "lucide-vue-next";
import RunControls from "../components/control/RunControls.vue";
import {
  useControlStore,
  type Config,
  conditionLabel,
} from "../stores/controlStore";
const control = useControlStore(),
  form = ref<Config>({}),
  source = ref("mock"),
  initialized = ref(false);
let loadedId: string | undefined;
watch(
  () => control.state,
  (state) => {
    if (!state) return;
    if (!initialized.value || (state.saved && state.saved.id !== loadedId)) {
      form.value = {
        ...(state.saved?.config ?? state.defaults),
        torque_off_on_normal_exit: false,
      };
      source.value = state.saved?.source ?? "mock";
      loadedId = state.saved?.id;
      initialized.value = true;
    }
  },
  { immediate: true },
);
const dirty = computed(
  () =>
    !control.state?.saved ||
    source.value !== control.state.saved.source ||
    JSON.stringify(form.value) !== JSON.stringify(control.state.saved.config),
);
const locked = computed(
  () => control.active || control.busy || control.state?.externalActive,
);
const conditions = [
  "normal",
  "friction",
  "overload",
  "overvoltage",
  "undervoltage",
  "undercurrent",
  "gear_backlash",
];
async function save() {
  await control.action("config", {
    source: source.value,
    config: {
      ...form.value,
      load_kg:
        form.value.condition_name === "overload" ? form.value.load_kg : 0,
    },
  });
}
</script>
<template>
  <div class="control-page">
    <div class="page-heading">
      <h2>제어</h2>
      <span class="subtle">왕복 완료 후 종료 · 토크 유지</span>
    </div>
    <form v-if="initialized" @submit.prevent="save">
      <fieldset :disabled="!!locked" class="control-form">
        <section class="panel control-section">
          <h3>모터 연결</h3>
          <div class="form-grid">
            <label
              >실행 대상<select aria-label="실행 대상" v-model="source">
                <option value="mock">가상 모터</option>
                <option value="real">실제 모터</option>
              </select></label
            >
            <label
              >모터 종류<select
                aria-label="모터 종류"
                v-model="form.motor_name"
              >
                <option>XM430-W210</option>
                <option>XM430-W350</option>
              </select></label
            >
            <label
              >모터 ID<input
                aria-label="모터 ID"
                v-model.number="form.motor_id"
                type="number"
                min="0"
                max="252"
                step="1"
                required
            /></label>
            <label
              >통신 포트<input
                aria-label="통신 포트"
                v-model="form.port"
                required
                placeholder="COM6"
            /></label>
            <label
              >통신 속도 (bps)<select
                aria-label="통신 속도 (bps)"
                v-model.number="form.baudrate"
              >
                <option
                  v-for="baud in [
                    9600, 57600, 115200, 1000000, 2000000, 3000000, 4000000,
                    4500000,
                  ]"
                  :value="baud"
                  :key="baud"
                >
                  {{ baud.toLocaleString() }}
                </option>
              </select></label
            >
          </div>
        </section>
        <section class="panel control-section">
          <h3>왕복 동작</h3>
          <div class="form-grid">
            <label
              >이동 회전수<input
                aria-label="이동 회전수"
                v-model.number="form.turns"
                type="number"
                min="0.001"
                max="511"
                step="any"
                required
            /></label>
            <label
              >이동 방향<select
                aria-label="이동 방향"
                v-model.number="form.direction"
              >
                <option :value="1">정방향 (+)</option>
                <option :value="-1">역방향 (−)</option>
              </select></label
            >
            <label
              >가속 시간 (ms)<input
                aria-label="가속 시간 (ms)"
                v-model.number="form.acceleration_ms"
                type="number"
                min="1"
                max="16383"
                required
            /></label>
            <label
              >편도 이동 시간 (ms)<input
                aria-label="편도 이동 시간 (ms)"
                v-model.number="form.profile_duration_ms"
                type="number"
                min="2"
                max="32767"
                required
            /></label>
            <label
              >상단 대기 (초)<input
                aria-label="상단 대기 (초)"
                v-model.number="form.top_dwell_sec"
                type="number"
                min="0"
                step="any"
                required
            /></label>
            <label
              >하단 대기 (초)<input
                aria-label="하단 대기 (초)"
                v-model.number="form.bottom_dwell_sec"
                type="number"
                min="0"
                step="any"
                required
            /></label>
            <label
              >왕복 횟수 · 0은 연속<input
                aria-label="왕복 횟수 · 0은 연속"
                v-model.number="form.max_cycles"
                type="number"
                min="0"
                max="1000000000"
                required
            /></label>
            <label
              >이동 제한 시간 (초)<input
                aria-label="이동 제한 시간 (초)"
                v-model.number="form.move_timeout_sec"
                type="number"
                min="0.01"
                step="any"
                required
            /></label>
          </div>
        </section>
        <section class="panel control-section">
          <h3>수집 및 실험 조건</h3>
          <div class="form-grid">
            <label
              >데이터 수집 주기 (초)<input
                aria-label="데이터 수집 주기 (초)"
                v-model.number="form.sample_interval_sec"
                type="number"
                min="0.02"
                max="10"
                step="any"
                required
            /></label>
            <label
              >실험 조건<select
                aria-label="실험 조건"
                v-model="form.condition_name"
              >
                <option
                  v-for="condition in conditions"
                  :value="condition"
                  :key="condition"
                >
                  {{ conditionLabel(condition) }}
                </option>
              </select></label
            >
            <label v-if="form.condition_name === 'overload'"
              >부하량 (kg)<input
                aria-label="부하량 (kg)"
                v-model.number="form.load_kg"
                type="number"
                min="0.001"
                step="any"
                required
            /></label>
          </div>
        </section>
        <div class="save-row">
          <span class="subtle">{{
            dirty ? "저장되지 않은 변경사항" : "설정 저장됨"
          }}</span
          ><button
            class="source-button"
            type="submit"
            :disabled="!dirty || !control.connected"
          >
            <Save :size="16" />설정 저장
          </button>
        </div>
      </fieldset>
    </form>
    <section class="panel control-section">
      <h3>실험 실행</h3>
      <RunControls :allow-start="!dirty" />
    </section>
  </div>
</template>
