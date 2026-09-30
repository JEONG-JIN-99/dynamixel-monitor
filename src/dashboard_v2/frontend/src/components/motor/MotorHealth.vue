<script setup lang="ts">
import { ShieldCheck } from "lucide-vue-next";
import { useMotorStore } from "../../stores/motorStore";
const store = useMotorStore();
const value = (n: number | null | undefined, decimals = 1) =>
  n == null ? "—" : n.toFixed(decimals);
</script>
<template>
  <section class="panel health-card">
    <div class="panel-title">
      <h2>Motor health</h2>
      <ShieldCheck :size="16" class="muted" />
    </div>
    <div class="health-row">
      <div>
        <span>Temperature</span
        ><strong
          >{{ value(store.latest?.temperature, 0) }} <small>°C</small></strong
        >
      </div>
      <div class="health-track"></div>
      <p>온도 한계값 <span>N/A</span></p>
    </div>
    <div class="health-row">
      <div>
        <span>Current load</span
        ><strong>{{ value(store.latest?.current, 3) }} <small>A</small></strong>
      </div>
      <div class="health-track"></div>
      <p>Current Limit 미확인 <span>N/A</span></p>
    </div>
    <div class="health-row">
      <div>
        <span>Input voltage</span
        ><strong>{{ value(store.latest?.voltage) }} <small>V</small></strong>
      </div>
      <div class="health-track"></div>
      <p>장치 허용 범위 <span>N/A</span></p>
    </div>
    <div class="info-note">
      CSV에 장치 한계값이 없어 건강도 비율을 계산하지 않습니다.
    </div>
  </section>
</template>
