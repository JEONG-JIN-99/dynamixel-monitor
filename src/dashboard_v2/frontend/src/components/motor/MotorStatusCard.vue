<script setup lang="ts">
import { Cpu, Activity } from "lucide-vue-next";
import { useMotorStore } from "../../stores/motorStore";
const store = useMotorStore();
</script>
<template>
  <section class="panel motor-card">
    <div class="panel-title">
      <h2>Selected motor</h2>
      <span class="tiny">01 / EXPERIMENT</span>
    </div>
    <div class="motor-select">
      <span class="motor-icon"><Cpu :size="27" /></span>
      <div>
        <strong>{{ store.experiment?.motorModel ?? "모터 선택 대기" }}</strong
        ><span>DYNAMIXEL · ID {{ store.experiment?.motorId ?? "—" }}</span>
      </div>
    </div>
    <div class="motor-status">
      <span
        class="badge"
        :class="
          store.latest?.hwError
            ? 'danger'
            : store.latest
              ? 'success'
              : 'neutral'
        "
        ><i class="dot"></i
        >{{
          !store.latest
            ? "NO DATA"
            : store.latest.hwError
              ? "HW ERROR"
              : "HW ERROR 없음"
        }}</span
      ><span class="tiny">마지막 CSV 측정 기준</span>
    </div>
    <div class="motor-fields">
      <div>
        <span>Movement</span
        ><strong
          ><Activity :size="13" />{{
            store.latest ? (store.latest.moving ? "Moving" : "Stopped") : "—"
          }}</strong
        >
      </div>
      <div>
        <span>Moving status</span
        ><strong>{{ store.latest?.movingStatus ?? "—" }}</strong>
      </div>
      <div>
        <span>Hardware error</span
        ><strong>{{ store.latest?.hwError ?? "—" }}</strong>
      </div>
      <div>
        <span>Realtime tick</span
        ><strong
          >{{ store.latest?.realtimeTick ?? "—" }} <small>ms</small></strong
        >
      </div>
      <div>
        <span>Cycle / Phase</span
        ><strong
          >{{ store.latest?.cycle ?? "—" }} /
          {{ store.latest?.phase ?? "—" }}</strong
        >
      </div>
    </div>
    <div class="motor-foot">
      <span>조건</span
      ><strong>{{
        store.latest?.condition ??
        store.metadata[0]?.settings.condition_name ??
        "—"
      }}</strong
      ><span>Firmware</span
      ><strong>{{ store.metadata[0]?.firmware ?? "N/A" }}</strong>
    </div>
  </section>
</template>
