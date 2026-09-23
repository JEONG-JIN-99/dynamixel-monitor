<script setup lang="ts">
import { ArrowLeft, PanelsTopLeft } from "lucide-vue-next";
</script>
<template>
  <section class="placeholder panel">
    <PanelsTopLeft :size="36" /><span class="eyebrow">PLANNED WORKSPACE</span>
    <h2>{{ $route.meta.title }}</h2>
    <p>
      이 페이지는 다음 개발 범위입니다.<br />실시간 측정값과 이벤트는
      Overview에서 확인할 수 있습니다.
    </p>
    <RouterLink
      :to="{
        path: '/',
        query: $route.query.source === 'mock' ? { source: 'mock' } : {},
      }"
      class="source-button"
      ><ArrowLeft :size="15" /> Overview로 돌아가기</RouterLink
    >
  </section>
</template>
