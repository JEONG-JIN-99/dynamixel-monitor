<script setup lang="ts">
import { computed, ref, defineAsyncComponent } from "vue";
import {
  Pause,
  Power,
  CircleHelp,
  ArrowRight,
  Activity,
} from "lucide-vue-next";
import { MOTOR_SLOTS, type MotorSlot } from "../../services/motorSlot";
import { useMotorStore } from "../../stores/motorStore";
import { useControlStore } from "../../stores/controlStore";
import { fleetStatus } from "../../services/fleetStatus";
import QuadrupedDiagram from "./QuadrupedDiagram.vue";
import "../../styles/fleet.css";
const selected = ref<MotorSlot>(1);
const view = ref<"diagram" | "model">("model");
const QuadrupedModel3D = defineAsyncComponent(() => import("./QuadrupedModel3D.vue"));
const positions = [
  { leg: "왼쪽 앞다리", joint: "몸통 관절", x: 35, y: 31 },
  { leg: "왼쪽 앞다리", joint: "무릎", x: 16, y: 19 },
  { leg: "오른쪽 앞다리", joint: "몸통 관절", x: 65, y: 31 },
  { leg: "오른쪽 앞다리", joint: "무릎", x: 84, y: 19 },
  { leg: "왼쪽 뒷다리", joint: "몸통 관절", x: 35, y: 66 },
  { leg: "왼쪽 뒷다리", joint: "무릎", x: 16, y: 79 },
  { leg: "오른쪽 뒷다리", joint: "몸통 관절", x: 65, y: 66 },
  { leg: "오른쪽 뒷다리", joint: "무릎", x: 84, y: 79 },
];
const stores = MOTOR_SLOTS.map((slot) => ({
  slot,
  control: useControlStore(slot),
  motor: useMotorStore(slot),
}));
const motors = computed(() =>
  stores.map(({ slot, control, motor }) => ({
    slot,
    control,
    ...positions[slot - 1],
    status: fleetStatus(
      control.state?.motorStatus,
      motor.latest,
      control.connected &&
        motor.connection === "connected" &&
        !(control.active && ["stale", "error"].includes(motor.system.validity)),
    ),
  })),
);
const chosen = computed(() =>
  motors.value.find((m) => m.slot === selected.value)!,
);
const running = computed(
  () => motors.value.filter((m) => m.status.moving === true).length,
);
async function toggle(slot: MotorSlot) {
  const { control } = stores[slot - 1];
  selected.value = slot;
  if (control.active && control.state?.run)
    await control.action("stop", { runId: control.state.run.runId });
  else if (control.state?.saved)
    await control.action("start", { configId: control.state.saved.id });
}
</script>
<template>
  <div class="fleet-overview">
    <section class="panel fleet-robot" aria-label="모터 위치">
      <div class="fleet-panel-heading">
        <h2>모터 위치</h2>
        <div class="fleet-view-switch" role="group" aria-label="로봇 보기 방식">
          <button :aria-pressed="view === 'diagram'" @click="view = 'diagram'">도면</button>
          <button :aria-pressed="view === 'model'" @click="view = 'model'">3D 모델</button>
        </div>
      </div>
      <QuadrupedModel3D v-if="view === 'model'" :motors="motors" :selected="selected" @select="selected = $event" @diagram="view = 'diagram'" />
      <QuadrupedDiagram v-else :motors="motors" :selected="selected" @select="selected = $event" />
      <div class="fleet-legend">
        <span><i class="running" />정상 동작</span
        ><span><i class="fault" />이상</span
        ><span><i class="idle">Ⅱ</i>멈춤</span
        ><span><i class="off" />전원 꺼짐</span
        ><span><CircleHelp :size="12" />미확인</span>
      </div>
      <div class="fleet-selected" aria-live="polite">
        <strong>모터 {{ chosen.slot }}</strong
        ><span>{{ chosen.leg }} · {{ chosen.joint }}</span>
        <div>
          전원 {{ chosen.status.powerLabel
          }}<span>동작 {{ chosen.status.movement }}</span
          ><span :class="chosen.status.diagnosisTone">{{
            chosen.status.diagnosis
          }}</span>
        </div>
      </div>
    </section>
    <section class="panel fleet-list" aria-label="모터별 상태 및 제어">
      <div class="fleet-panel-heading">
        <h2>모터 상태</h2>
        <span>동작중 {{ running }} / 8</span>
      </div>
      <div class="fleet-row-label">
        <span>모터 / 위치</span><span>진단 / 동작</span><span>제어</span>
      </div>
      <div
        v-for="m in motors"
        :key="m.slot"
        class="fleet-row"
        :class="{ picked: selected === m.slot }"
        :data-motor="m.slot"
      >
        <RouterLink
          class="fleet-open"
          :to="{ path: '/', query: { motor: String(m.slot) } }"
          :aria-label="`모터 ${m.slot} 개요 보기`"
          ><strong>모터 {{ m.slot }}</strong
          ><small><span>{{ m.leg }}</span> <span>{{ m.joint }}</span></small>
          <span>개요 보기 <ArrowRight :size="12" /></span
        ></RouterLink>
        <div class="fleet-state">
          <strong :class="m.status.diagnosisTone">{{
            m.status.diagnosis
          }}</strong
          ><span
            ><component
              :is="
                m.status.moving
                  ? Activity
                  : m.status.power === 'off'
                    ? Power
                    : Pause
              "
              :size="13"
            />{{ m.status.powerLabel }} ·
            {{
              m.control.state?.run?.status === "finishing"
                ? "종료 대기"
                : m.status.movement
            }}</span
          >
        </div>
        <div class="fleet-actions">
          <RouterLink
            v-if="!m.control.state?.saved"
            class="fleet-action"
            :to="{ path: '/control', query: { motor: String(m.slot) } }"
            :aria-label="`모터 ${m.slot} 설정`"
            >설정</RouterLink
          ><button
            v-else
            class="fleet-action"
            :aria-label="`모터 ${m.slot} ${m.control.active ? '종료' : '시작'}`"
            :disabled="
              !m.control.connected ||
              m.control.busy ||
              m.control.state?.externalActive ||
              m.control.state?.run?.status === 'finishing'
            "
            @click="toggle(m.slot)"
          >
            {{
              m.control.state?.run?.status === "finishing"
                ? "대기"
                : m.control.active
                  ? "종료"
                  : "시작"
            }}
          </button>
        </div>
        <p
          v-if="m.control.error || m.control.state?.run?.error"
          class="control-error fleet-error"
          role="alert"
        >
          {{ m.control.error || m.control.state?.run?.error }}
        </p>
      </div>
    </section>
  </div>
</template>
