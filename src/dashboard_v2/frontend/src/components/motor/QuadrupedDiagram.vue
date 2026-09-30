<script setup lang="ts">
import { ArrowUp, Pause, TriangleAlert, Power, CircleHelp } from "lucide-vue-next";
import type { MotorSlot } from "../../services/motorSlot";
defineProps<{
  motors: { slot: MotorSlot; leg: string; joint: string; status: { tone: string; diagnosis: string; movement: string } }[];
  selected: MotorSlot;
}>();
const emit = defineEmits<{ select: [slot: MotorSlot] }>();
const legs = [
  { name: "왼쪽 앞다리", x: 190, y: 185, side: 1, slots: [1, 2] },
  { name: "오른쪽 앞다리", x: 410, y: 185, side: -1, slots: [3, 4] },
  { name: "왼쪽 뒷다리", x: 190, y: 460, side: 1, slots: [5, 6] },
  { name: "오른쪽 뒷다리", x: 410, y: 460, side: -1, slots: [7, 8] },
];
const points = legs.flatMap((leg) => [
  { x: leg.x, y: leg.y, left: leg.side === 1 },
  { x: leg.x - 55 * leg.side, y: leg.y + 111, left: leg.side === 1 },
]);
const icons = { idle: Pause, fault: TriangleAlert, off: Power, unknown: CircleHelp };
</script>
<template>
  <div class="explorer-diagram">
    <div class="explorer-viewport">
    <div class="explorer-stage">
      <svg class="explorer-drawing" viewBox="0 0 600 720" role="img" aria-label="백색 탐사형 4족 로봇 평면도: 각 다리의 몸통 관절과 무릎에 배치된 모터 1~8">
        <!-- Flat, mirrored armor plates: all state colors are separate live overlays. -->
        <g stroke="#131c28" stroke-width="2.2" stroke-linejoin="round">
          <g v-for="leg in legs" :key="leg.x + ':' + leg.y" :transform="`translate(${leg.x} ${leg.y}) scale(${leg.side} 1)`">
            <path d="M19 -14 H60 V17 H19Z" fill="#343f4d" />
            <path d="M31 -18 H42 V20 H31Z M50 -13 H59 V16 H50Z" fill="#657080" />
            <path d="M-18 -44 L10 -45 L27 -24 L24 22 L-6 36 L-29 12 L-32 -19Z" fill="#e4e5e2" />
            <path d="M-11 -38 L6 -39 L17 -23 L12 -10 L-13 -12 L-22 -23Z" fill="#b2bac2" />
            <path d="M-16 18 L8 33 L-29 100 L-56 117 L-76 101 L-66 76Z" fill="#ecece6" />
            <path d="M-13 32 L-54 91 L-61 100 M-60 80 L-51 85" fill="none" stroke="#88939e" stroke-width="1.5" />
            <path d="M-64 126 L-40 139 L-64 185 L-88 196 L-103 180 L-90 151Z" fill="#e5e7e4" />
            <path d="M-55 143 L-79 183 M-91 161 L-84 165" fill="none" stroke="#89949e" stroke-width="1.5" />
            <path d="M-102 176 L-80 175 L-65 191 L-68 211 L-85 221 L-111 218 L-123 204 L-117 186Z" fill="#343f4b" />
            <path d="M-102 185 L-84 183 L-75 194 L-78 206 L-89 212 L-108 208 L-114 199Z" fill="#4e5a68" />
            <path d="M-93 169 L-76 176 L-80 193 L-88 196 L-101 187Z" fill="#d8dddF" />
            <circle cx="0" cy="0" r="31" fill="#78828e" />
            <circle cx="0" cy="0" r="24" fill="#283543" />
            <circle cx="-55" cy="111" r="28" fill="#78828e" />
            <circle cx="-55" cy="111" r="21" fill="#283543" />
          </g>
          <!-- White exploration shell: sensor at the front, inset frame and flat seams. -->
          <path d="M278 78 H322 L351 107 L367 176 V410 L353 517 L326 568 H274 L247 517 L233 410 V176 L249 107Z" fill="#303e4d" />
          <path d="M278 78 H322 L348 106 L346 146 L331 169 H269 L254 146 L252 106Z" fill="#e9e9e3" />
          <path d="M278 105 H322 L334 117 V137 L322 147 H278 L266 137 V117Z" fill="#273543" />
          <path d="M274 124 L281 118 H319 L326 124" fill="none" stroke="#70b6de" stroke-width="3" />
          <path d="M265 157 H335 L344 249 L337 338 L352 412 L331 443 H269 L248 412 L263 338 L256 249Z" fill="#eeeee8" />
          <path d="M253 153 L237 181 L239 271 L254 303 L262 251Z M347 153 L363 181 L361 271 L346 303 L338 251Z" fill="#dfe3e1" />
          <path d="M253 308 L239 281 V399 L250 426 L263 375Z M347 308 L361 281 V399 L350 426 L337 375Z" fill="#dfe3e1" />
          <path d="M269 447 H331 L344 476 L334 534 L319 560 H281 L266 534 L256 476Z" fill="#e6e8e3" />
          <path d="M286 420 H314 L324 434 L318 463 H282 L276 434Z" fill="#53606e" />
          <path d="M288 530 H312 V561 H288Z" fill="#53606e" />
          <rect x="292" y="170" width="16" height="27" rx="3" fill="#53606e" />
          <path d="M269 231 V270 M331 231 V270 M286 499 H314" stroke="#4c5968" stroke-width="4" fill="none" />
          <path d="M271 158 L278 145 M329 158 L322 145 M260 310 L270 330 M340 310 L330 330" stroke="#89949f" stroke-width="1.3" fill="none" />
        </g>
        <g class="explorer-leaders" fill="none" stroke-width="1.5">
          <path v-for="m in motors" :key="m.slot" :class="m.status.tone"
            :d="points[m.slot-1]!.left
              ? `M8 ${points[m.slot-1]!.y - 14} H70 L91 ${points[m.slot-1]!.y} H${points[m.slot-1]!.x - 33}`
              : `M592 ${points[m.slot-1]!.y - 14} H530 L509 ${points[m.slot-1]!.y} H${points[m.slot-1]!.x + 33}`" />
        </g>
      </svg>
      <div class="explorer-front"><ArrowUp :size="14" />앞쪽</div>
      <span v-for="leg in legs" :key="leg.name" class="explorer-leg" :class="{ right: leg.side === -1 }" :style="{ top: (leg.y - (leg.y > 200 ? 50 : 78)) / 720 * 100 + '%' }">{{ leg.name }}</span>
      <span v-for="m in motors" :key="'label'+m.slot" class="explorer-callout" :class="{ right: !points[m.slot-1]!.left }" :style="{ top: (points[m.slot-1]!.y - 30) / 720 * 100 + '%' }"><b>{{ m.slot }}</b>{{ m.joint }}</span>
      <button v-for="m in motors" :key="m.slot" class="fleet-marker explorer-marker" :class="[m.status.tone, { picked: selected === m.slot }]"
        :style="{ left: points[m.slot-1]!.x / 600 * 100 + '%', top: points[m.slot-1]!.y / 720 * 100 + '%' }"
        :aria-label="`모터 ${m.slot}, ${m.leg} ${m.joint}, ${m.status.diagnosis}, ${m.status.movement}`" :aria-pressed="selected === m.slot" @click="emit('select', m.slot)">
        <b>{{ m.slot }}</b><component v-if="m.status.tone in icons" :is="icons[m.status.tone as keyof typeof icons]" :size="12" class="explorer-status-icon" />
      </button>
    </div>
    </div>
    <div class="explorer-compact-labels">
      <div v-for="leg in legs" :key="leg.name"><strong>{{ leg.name }}</strong><span>{{ leg.slots[0] }} 몸통 관절 · {{ leg.slots[1] }} 무릎</span></div>
    </div>
    <div class="explorer-roles"><span><b>몸통 관절</b>다리 앞뒤 회전</span><span><b>무릎</b>다리 굽힘·폄</span></div>
  </div>
</template>
<style scoped>
.explorer-diagram { container-type: inline-size; margin: 0 12px; }
.explorer-viewport { width: 100%; }
.explorer-stage { position: relative; width: 100%; aspect-ratio: 600/720; }
.explorer-drawing { display: block; width: 100%; height: 100%; }
.explorer-front { position: absolute; left: 50%; top: 1.5%; transform: translateX(-50%); display: flex; gap: 4px; align-items: center; font-size: 12px; color: #b8cce3; }
.explorer-leg { position: absolute; left: 1%; font-size: 12px; color: #c3d5eb; font-weight: 600; }
.explorer-leg.right { left: auto; right: 1%; }
.explorer-callout { position: absolute; left: 1%; display: flex; align-items: center; gap: 6px; font-size: 11px; color: #b7cce5; }
.explorer-callout.right { left: auto; right: 1%; }
.explorer-callout b { color: #e1eaf6; }
.explorer-leaders { stroke: #65d9b0; }
.explorer-leaders .fault { stroke: #ff818b; }
.explorer-leaders .off, .explorer-leaders .unknown { stroke: #8295ae; stroke-dasharray: 4 3; }
.explorer-marker { width: clamp(29px, 6.7cqw, 40px); height: clamp(29px, 6.7cqw, 40px); box-shadow: none; }
.explorer-marker b { position: static; background: none; border: 0; padding: 0; height: auto; min-width: 0; color: inherit; font-size: clamp(15px, 3.7cqw, 21px); }
.explorer-status-icon { position: absolute; right: -7px; bottom: -6px; background: #162333; border-radius: 3px; box-shadow: 0 0 0 2px #162333; }
.explorer-roles { display: flex; justify-content: center; flex-wrap: wrap; gap: 8px 20px; font-size: 11px; color: #9db3cd; padding: 8px 0 6px; }
.explorer-roles span { display: flex; gap: 6px; }
.explorer-roles b { color: #c2d4e9; font-weight: 500; }
.explorer-compact-labels { display: none; }
@container (max-width: 420px) {
  .explorer-callout, .explorer-leaders, .explorer-leg { display: none; }
  .explorer-compact-labels { display: grid; grid-template-columns: 1fr 1fr; gap: 12px 8px; padding: 8px 4px; font-size: 11px; }
  .explorer-compact-labels strong { display: block; color: #c2d4e9; font-weight: 500; margin-bottom: 3px; }
  .explorer-compact-labels span { color: #9db3cd; }
}
@media (min-width: 1100px) and (min-height: 620px) {
  .explorer-diagram { flex: 1; min-height: 0; display: flex; flex-direction: column; }
  .explorer-viewport { flex: 1; min-height: 0; container-type: size; display: grid; place-items: center; }
  .explorer-stage { width: min(100cqw, 83.333cqh); container-type: inline-size; }
  .explorer-compact-labels { display: none; }
  .explorer-roles { flex-shrink: 0; padding: 4px 0; }
}
</style>
