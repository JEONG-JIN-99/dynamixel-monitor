<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, watch } from "vue";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { buildExplorerModel, type ExplorerJoint } from "./explorerModel";
import { RotateCcw, Rotate3D } from "lucide-vue-next";
import type { MotorSlot } from "../../services/motorSlot";

const props = defineProps<{
  motors: { slot: MotorSlot; status: { tone: string; diagnosis: string; movement: string } }[];
  selected: MotorSlot;
}>();
const emit = defineEmits<{ select: [slot: MotorSlot]; diagram: [] }>();
const host = ref<HTMLDivElement>();
const ready = ref(false), unavailable = ref(false), rotating = ref(false);
const cameraView = ref("");
const labels = ref<{ slot: MotorSlot; x: number; y: number; visible: boolean }[]>([]);
const colors: Record<string, number> = {
  running: 0x00dd68, fault: 0xff1638, idle: 0x00dd68, off: 0x89939e, unknown: 0x89939e,
};
let renderer: THREE.WebGLRenderer | undefined;
let controls: OrbitControls | undefined;
let observer: ResizeObserver | undefined;
let scene: THREE.Scene, camera: THREE.PerspectiveCamera;
let dirty = true, disposed = false, previousTime = 0;
const joints: ExplorerJoint[] = [];
const target = new THREE.Vector3(0, 1.75, 0);

function updateStatus() {
  for (const joint of joints) {
    const motor = props.motors.find((m) => m.slot === joint.slot);
    const color = colors[motor?.status.tone ?? "unknown"] ?? colors.unknown!;
    joint.material.color.setHex(color);
    joint.material.emissive.setHex(color);
    joint.material.emissiveIntensity = ["running", "idle", "fault"].includes(motor?.status.tone ?? "") ? .9 : .05;
    joint.ring.visible = props.selected === joint.slot;
  }
  dirty = true;
}
watch(() => [props.motors, props.selected], updateStatus, { deep: true });
watch(rotating, (value) => { if (controls) controls.autoRotate = value; dirty = true; });

function reset() {
  if (!camera || !controls || !host.value) return;
  rotating.value = false;
  controls.target.copy(target);
  const aspect = host.value.clientWidth / Math.max(1, host.value.clientHeight);
  const distance = 10.6 * Math.max(1, 1 / aspect);
  camera.position.copy(target).addScaledVector(new THREE.Vector3(7, 4.0, 9).normalize(), distance);
  controls.update();
  dirty = true;
}
function resize() {
  if (!host.value || !renderer) return;
  const { width, height } = host.value.getBoundingClientRect();
  if (!width || !height) return;
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
  dirty = true;
}
function keyboard(event: KeyboardEvent) {
  if (!controls || !camera) return;
  const keys = ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "+", "=", "-"];
  if (!keys.includes(event.key)) return;
  event.preventDefault();
  rotating.value = false;
  const spherical = new THREE.Spherical().setFromVector3(camera.position.clone().sub(controls.target));
  if (event.key === "ArrowLeft") spherical.theta -= .15;
  if (event.key === "ArrowRight") spherical.theta += .15;
  if (event.key === "ArrowUp") spherical.phi -= .1;
  if (event.key === "ArrowDown") spherical.phi += .1;
  if (event.key === "+" || event.key === "=") spherical.radius *= .9;
  if (event.key === "-") spherical.radius *= 1.1;
  spherical.phi = THREE.MathUtils.clamp(spherical.phi, .15, Math.PI / 2 - .04);
  spherical.radius = THREE.MathUtils.clamp(spherical.radius, 5, 28);
  camera.position.copy(controls.target).add(new THREE.Vector3().setFromSpherical(spherical));
  controls.update();
  dirty = true;
}
function contextLost(event: Event) {
  event.preventDefault();
  unavailable.value = true;
  renderer?.setAnimationLoop(null);
}

onMounted(() => {
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x162333);
  scene.fog = new THREE.Fog(0x162333, 15, 40);
  camera = new THREE.PerspectiveCamera(38, 1, .1, 100);
  try {
    renderer = new THREE.WebGLRenderer({ antialias: true });
  } catch {
    unavailable.value = true;
    return;
  }
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.25;
  renderer.domElement.setAttribute("aria-label", "4족 로봇 3D 모델. 방향키로 회전, 더하기와 빼기로 확대 및 축소");
  renderer.domElement.tabIndex = 0;
  renderer.domElement.addEventListener("keydown", keyboard);
  renderer.domElement.addEventListener("webglcontextlost", contextLost);
  host.value!.appendChild(renderer.domElement);
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enablePan = false;
  controls.enableDamping = true;
  controls.dampingFactor = .12;
  controls.minDistance = 5;
  controls.maxDistance = 28;
  controls.minPolarAngle = .15;
  controls.maxPolarAngle = Math.PI / 2 - .04;
  controls.autoRotateSpeed = .7;
  controls.addEventListener("change", () => { dirty = true; });
  controls.addEventListener("start", () => { rotating.value = false; });
  scene.add(new THREE.HemisphereLight(0xdeedff, 0x253347, 2.3));
  const light = new THREE.DirectionalLight(0xffffff, 2.5);
  light.position.set(4, 8, 5);
  light.castShadow = true;
  light.shadow.mapSize.set(2048, 2048);
  Object.assign(light.shadow.camera, { left: -5, right: 5, top: 5, bottom: -5, near: .5, far: 25 });
  light.shadow.normalBias = .03;
  const rim = new THREE.DirectionalLight(0xa9cbff, 3);
  rim.position.set(-4, 5, -4);
  scene.add(rim);
  scene.add(light);
  joints.push(...buildExplorerModel(scene));
  updateStatus();
  observer = new ResizeObserver(resize);
  observer.observe(host.value!);
  resize();
  reset();
  renderer.setAnimationLoop((now) => {
    if (disposed || !renderer || !controls) return;
    controls.update(previousTime ? Math.min((now - previousTime) / 1000, .1) : 0);
    previousTime = now;
    if (!dirty) return;
    renderer.render(scene, camera);
    cameraView.value = camera.position.toArray().map((n) => n.toFixed(3)).join(",");
    labels.value = joints.map(({ slot, anchor }) => {
      const point = anchor.clone().project(camera);
      return { slot, x: (point.x + 1) * 50, y: (1 - point.y) * 50,
        visible: point.z > -1 && point.z < 1 && Math.abs(point.x) < .95 && Math.abs(point.y) < .95 };
    });
    ready.value = true;
    dirty = false;
  });
});
onBeforeUnmount(() => {
  disposed = true;
  observer?.disconnect();
  controls?.dispose();
  renderer?.setAnimationLoop(null);
  const materials = new Set<THREE.Material>();
  scene?.traverse((object) => {
    if (object instanceof THREE.Mesh || object instanceof THREE.Line || object instanceof THREE.LineSegments) {
      object.geometry.dispose();
      (Array.isArray(object.material) ? object.material : [object.material]).forEach((m) => materials.add(m));
    }
  });
  materials.forEach((material) => material.dispose());
  renderer?.domElement.removeEventListener("keydown", keyboard);
  renderer?.domElement.removeEventListener("webglcontextlost", contextLost);
  renderer?.dispose();
  renderer?.domElement.remove();
});
</script>
<template>
  <div class="quadruped-view">
    <div class="quadruped-tools">
      <button :aria-pressed="rotating" :disabled="unavailable" @click="rotating = !rotating"><Rotate3D :size="14" />자동 회전</button>
      <button :disabled="unavailable" @click="reset"><RotateCcw :size="14" />처음 시점</button>
    </div>
    <div ref="host" class="quadruped-canvas" :data-ready="ready" :data-camera="cameraView" aria-label="4족 로봇 3D 보기">
      <template v-if="!unavailable">
        <button v-for="label in labels" :key="label.slot" v-show="label.visible"
          class="quadruped-label" :class="[motors.find(m => m.slot === label.slot)?.status.tone, { picked: selected === label.slot }]"
          :style="{ left: label.x + '%', top: label.y + '%' }" :aria-pressed="selected === label.slot"
          :aria-label="`3D 모터 ${label.slot} 선택, ${motors.find(m => m.slot === label.slot)?.status.diagnosis}`"
          @click="emit('select', label.slot)">{{ label.slot }}</button>
      </template>
      <div v-else class="quadruped-fallback"><p>3D 화면을 표시할 수 없습니다.</p><button @click="emit('diagram')">도면 보기</button></div>
    </div>
    <p class="quadruped-hint">드래그로 회전 · 휠로 확대 · 번호를 눌러 모터 선택</p>
  </div>
</template>
<style scoped>
.quadruped-view { margin: 0 12px; }
.quadruped-tools { display: flex; justify-content: flex-end; gap: 8px; margin-bottom: 10px; flex-wrap: wrap; }
.quadruped-tools button, .quadruped-fallback button { display: inline-flex; align-items: center; gap: 5px; border: 1px solid #40566e; border-radius: 6px; background: #203248; padding: 7px 9px; font-size: 12px; }
.quadruped-tools button[aria-pressed=true] { color: #8ce4d2; border-color: #59d6b2; }
.quadruped-canvas { position: relative; width: 100%; aspect-ratio: 440/500; overflow: hidden; border-radius: 8px; background: #162333; }
.quadruped-canvas :deep(canvas) { display: block; width: 100%; height: 100%; touch-action: none; cursor: grab; }
.quadruped-canvas :deep(canvas:active) { cursor: grabbing; }
.quadruped-canvas :deep(canvas:focus-visible) { outline: 3px solid #2266b5; outline-offset: -3px; }
.quadruped-label { position: absolute; z-index: 1; transform: translate(-50%, -50%); width: 29px; height: 29px; border: 1.5px solid #667787; border-radius: 50%; color: #405166; background: #f5f7fa; box-shadow: 0 2px 5px #18243630; padding: 0; font-size: 12px; font-weight: 700; }
.quadruped-label.running, .quadruped-label.idle { background: #00dd68; color: #052718; border-color: #80ffb4; box-shadow: 0 0 10px #00dd6866, 0 2px 5px #07152280; }
.quadruped-label.fault { background: #ff3150; color: #300510; border-color: #ff97a7; box-shadow: 0 0 10px #ff315080, 0 2px 5px #07152280; }
.quadruped-label.off, .quadruped-label.unknown { border-style: dashed; }
.quadruped-label.picked { outline: 2px solid #2266b5; outline-offset: 3px; }
.quadruped-hint { margin: 10px 0 0; color: #9eb3cd; font-size: 11px; text-align: center; line-height: 1.6; }
.quadruped-fallback { padding: 30px 15px; color: #405166; text-align: center; }
@media (min-width: 1100px) and (min-height: 620px) {
  .quadruped-view { flex: 1; min-height: 0; display: flex; flex-direction: column; }
  .quadruped-tools { flex-shrink: 0; margin-bottom: 6px; }
  .quadruped-canvas { flex: 1; min-height: 0; aspect-ratio: auto; }
  .quadruped-hint { flex-shrink: 0; margin-top: 5px; }
}
</style>
