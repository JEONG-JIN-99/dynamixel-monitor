<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";
import { ArrowLeft } from "lucide-vue-next";
import MotorSelector from "../components/MotorSelector.vue";
import MotorScope from "../components/MotorScope.vue";
import RobotOverview from "../components/motor/RobotOverview.vue";
import { parseMotorSlot } from "../services/motorSlot";
import OverviewView from "./OverviewView.vue";
const route = useRoute();
const selected = computed(() => parseMotorSlot(route.query.motor));
</script>
<template>
  <div class="dual-page-heading">
    <div class="fleet-page-title">
      <RouterLink
        v-if="selected"
        class="source-button fleet-back"
        :to="{ path: '/' }"
        ><ArrowLeft :size="15" />전체 개요</RouterLink
      >
      <h2>{{ selected ? `모터 ${selected} 개요` : "개요" }}</h2>
    </div>
    <MotorSelector v-if="selected" select />
    <span v-else class="subtle">4족 보행 로봇 · 8개 모터</span>
  </div>
  <MotorScope v-if="selected" :key="selected" :slot="selected"
    ><OverviewView
  /></MotorScope>
  <RobotOverview v-else />
</template>
