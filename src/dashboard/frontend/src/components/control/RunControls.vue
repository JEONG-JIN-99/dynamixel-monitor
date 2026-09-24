<script setup lang="ts">
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { Play, Square } from "lucide-vue-next";
import { useControlStore, statusLabel } from "../../stores/controlStore";
const props = withDefaults(
  defineProps<{ allowStart?: boolean; showTarget?: boolean }>(),
  {
    allowStart: true,
    showTarget: true,
  },
);
const control = useControlStore(),
  route = useRoute(),
  router = useRouter();
const target = computed(() => (control.active ? control.state?.run : null));
async function start() {
  const saved = control.state?.saved;
  if (!saved) return;
  if (await control.action("start", { configId: saved.id }))
    await router.replace({
      path: route.path,
      query: {
        ...route.query,
        source: saved.source === "mock" ? "mock" : "csv",
      },
    });
}
async function stop() {
  if (control.state?.run)
    await control.action("stop", { runId: control.state.run.runId });
}
</script>
<template>
  <div class="run-controls">
    <div class="run-state" :class="control.state?.run?.status">
      <span>{{
        control.state?.externalActive
          ? "다른 실험 진행 중"
          : statusLabel(control.state?.run?.status)
      }}</span
      ><small v-if="props.showTarget"
        >{{
          (target?.motorModel ?? control.state?.saved?.config.motor_name) ||
          "설정 대기"
        }}<template v-if="target || control.state?.saved">
          · ID {{ target?.motorId ?? control.state?.saved?.config.motor_id }} ·
          {{
            (target?.source ?? control.state?.saved?.source) === "mock"
              ? "가상 모터"
              : "실제 모터"
          }}</template
        ></small
      >
    </div>
    <div class="run-buttons">
      <button
        class="run-start"
        :disabled="
          !props.allowStart ||
          !control.connected ||
          !control.state?.saved ||
          control.active ||
          control.state?.externalActive ||
          control.busy
        "
        @click="start"
      >
        <Play :size="15" />실험 시작
      </button>
      <button
        class="run-stop"
        :disabled="
          !control.connected ||
          !control.active ||
          control.state?.run?.status === 'finishing' ||
          control.busy
        "
        @click="stop"
      >
        <Square :size="14" />{{
          control.state?.run?.status === "finishing" ? "종료 대기" : "실험 종료"
        }}
      </button>
    </div>
    <p v-if="!control.connected" class="control-error" role="status">
      제어 서버 연결 대기
    </p>
    <p v-if="control.error" class="control-error" role="alert">
      {{ control.error }}
    </p>
    <p
      v-else-if="control.state?.run?.error"
      class="control-error"
      role="status"
    >
      {{ control.state.run.error }}
    </p>
  </div>
</template>
