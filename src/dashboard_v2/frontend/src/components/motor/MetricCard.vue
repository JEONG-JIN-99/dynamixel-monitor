<script setup lang="ts">
defineProps<{
  label: string;
  value: number | null | undefined;
  unit: string;
  detail: string;
  color: string;
  decimals?: number;
}>();
</script>
<template>
  <article class="metric-card" :style="{ '--accent': color }">
    <div class="metric-label">
      <span class="metric-dot"></span>{{ label
      }}<span class="metric-tag">PRESENT</span>
    </div>
    <div class="metric-value">
      {{
        value == null
          ? "—"
          : value.toLocaleString("en-US", {
              minimumFractionDigits: decimals ?? 1,
              maximumFractionDigits: decimals ?? 1,
            })
      }}<span>{{ unit }}</span>
    </div>
    <div class="metric-detail">{{ detail }}</div>
  </article>
</template>
