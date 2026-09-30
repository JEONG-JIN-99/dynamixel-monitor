<script setup lang="ts">
import { provide } from "vue";
import { motorSlotKey, type MotorSlot } from "../services/motorSlot";
const props = defineProps<{ slot: MotorSlot }>();
provide(motorSlotKey, props.slot);
</script>
<template><slot /></template>
