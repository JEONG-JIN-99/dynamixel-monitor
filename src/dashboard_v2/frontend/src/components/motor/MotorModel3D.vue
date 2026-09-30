<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, watch } from "vue";
import * as THREE from "three";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import { shaftAngle, shaftDegrees } from "../../services/shaftRotation";
const props = defineProps<{
  position: number | null;
  origin: number | null;
  context: string;
  model: string;
  intervalMs: number;
}>();
const host = ref<HTMLDivElement>();
const ready = ref(false),
  fallback = ref(false);
const shownAngle = ref(0);
let renderer: THREE.WebGLRenderer | undefined;
let scene: THREE.Scene, camera: THREE.PerspectiveCamera, rotor: THREE.Group;
let observer: ResizeObserver | undefined;
let disposed = false,
  current = 0,
  from = 0,
  target = 0,
  started = 0,
  duration = 0,
  dirty = true;
let lastContext = "",
  initialized = false;
let modelBounds: THREE.Box3;
const reduced =
  typeof matchMedia === "function" &&
  matchMedia("(prefers-reduced-motion: reduce)").matches;
function update() {
  if (props.context !== lastContext) {
    lastContext = props.context;
    initialized = false;
    current = 0;
    target = 0;
    duration = 0;
  }
  if (
    !Number.isFinite(props.position) ||
    !Number.isFinite(props.origin) ||
    props.position == null ||
    props.origin == null
  ) {
    duration = 0;
    target = current;
    dirty = true;
    return;
  }
  const next = shaftAngle(props.position, props.origin);
  if (!initialized || reduced) {
    current = next;
    target = next;
    duration = 0;
    initialized = true;
  } else if (next !== target) {
    from = current;
    target = next;
    started = performance.now();
    duration = Math.min(
      1400,
      Math.max(
        80,
        props.intervalMs,
        (Math.abs(target - from) / (Math.PI * 2)) * 350,
      ),
    );
  }
  dirty = true;
}
watch(() => [props.position, props.origin, props.context], update, {
  immediate: true,
});
function resize() {
  if (!renderer || !host.value) return;
  const { width, height } = host.value.getBoundingClientRect();
  if (!width || !height) return;
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.fov = 34;
  camera.zoom = 1;
  // Fit all eight model corners, keeping a clear margin at every aspect ratio.
  const center = modelBounds.getCenter(new THREE.Vector3());
  const direction = new THREE.Vector3(48, 30, 78).normalize();
  camera.position.copy(center).add(direction);
  camera.lookAt(center);
  const inverse = camera.quaternion.clone().invert();
  const tanY = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
  const tanX = tanY * camera.aspect;
  let distance = 0;
  for (const x of [modelBounds.min.x, modelBounds.max.x])
    for (const y of [modelBounds.min.y, modelBounds.max.y])
      for (const z of [modelBounds.min.z, modelBounds.max.z]) {
        const corner = new THREE.Vector3(x, y, z)
          .sub(center)
          .applyQuaternion(inverse);
        distance = Math.max(
          distance,
          corner.z +
            Math.max(Math.abs(corner.x) / tanX, Math.abs(corner.y) / tanY) /
              0.94,
        );
      }
  camera.position.copy(center).addScaledVector(direction, distance);
  camera.updateProjectionMatrix();
  camera.lookAt(center);
  dirty = true;
}
function tick(now: number) {
  if (disposed) return;
  if (duration > 0) {
    const t = Math.min(1, (now - started) / duration);
    current = from + (target - from) * t;
    if (t === 1) duration = 0;
    dirty = true;
  }
  if (!dirty) return;
  shownAngle.value = current;
  // Viewed from the front: positive pulse values turn counterclockwise.
  if (rotor) rotor.rotation.z = current;
  if (renderer && scene) {
    renderer.render(scene, camera);
    ready.value = true;
  }
  dirty = false;
}
onMounted(() => {
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(34, 1, 0.1, 500);
  try {
    renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    renderer.setClearColor(0x000000, 0);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.5;
    renderer.domElement.setAttribute("aria-hidden", "true");
    host.value!.appendChild(renderer.domElement);
  } catch {
    fallback.value = true;
  }
  const dark = new THREE.MeshStandardMaterial({
    color: 0x242527,
    roughness: 0.57,
    metalness: 0.35,
  });
  const edge = new THREE.MeshStandardMaterial({
    color: 0x17181a,
    roughness: 0.6,
    metalness: 0.25,
  });
  const metal = new THREE.MeshStandardMaterial({
    color: 0xbfc0be,
    roughness: 0.38,
    metalness: 0.65,
  });
  const black = new THREE.MeshStandardMaterial({
    color: 0x090a0b,
    roughness: 0.65,
    metalness: 0.15,
  });
  const teal = new THREE.MeshStandardMaterial({
    color: 0x69dfbf,
    emissive: 0x164b3c,
    roughness: 0.35,
    metalness: 0.2,
  });
  function box(
    w: number,
    h: number,
    d: number,
    x: number,
    y: number,
    z: number,
    mat: THREE.Material = dark,
    round = 1.2,
  ) {
    const mesh = new THREE.Mesh(new RoundedBoxGeometry(w, h, d, 3, round), mat);
    mesh.position.set(x, y, z);
    scene.add(mesh);
    return mesh;
  }
  function cylinder(
    r: number,
    depth: number,
    x: number,
    y: number,
    z: number,
    mat: THREE.Material,
    parent: THREE.Object3D = scene,
  ) {
    const mesh = new THREE.Mesh(
      new THREE.CylinderGeometry(r, r, depth, 48),
      mat,
    );
    mesh.rotation.x = Math.PI / 2;
    mesh.position.set(x, y, z);
    parent.add(mesh);
    return mesh;
  }
  // Match the reference: deep black case, plain face and a six-hole silver horn.
  box(28, 44, 37, 0, 0, 0, dark, 1.8);
  box(28.4, 43.7, 3.4, 0, 0, -17.5, edge, 1.4);
  box(28.5, 43.7, 3.4, 0, 0, 17.7, edge, 1.4);
  box(27.2, 42, 1.8, 0, 0, 19.3, dark, 1.3);
  // Front fixing screws and recessed vertical mounting slots.
  for (const x of [-10.8, 10.8]) {
    box(3.5, 15, 0.7, x, -7.5, 20.4, black, 1.2);
    for (const y of [-18, 18]) {
      cylinder(2.05, 0.7, x, y, 20.5, black);
      cylinder(1.45, 0.85, x, y, 20.9, metal);
      const socket = new THREE.Mesh(
        new THREE.CylinderGeometry(0.85, 0.85, 0.2, 6),
        black,
      );
      socket.rotation.x = Math.PI / 2;
      socket.position.set(x, y, 21.4);
      scene.add(socket);
    }
    for (const y of [-13, -2]) {
      cylinder(1.25, 0.4, x, y, 20.9, black);
    }
  }
  // Round side mounting holes and the rear cover seam.
  for (const x of [-14.2, 14.2]) {
    for (const z of [-14, 13]) {
      box(0.35, 38, 0.35, x, 0, z, black, 0.1);
      for (const y of [-17, -11, 10, 16]) {
        const hole = cylinder(1.25, 0.5, x, y, z, black);
        hole.rotation.set(0, 0, Math.PI / 2);
      }
    }
  }
  for (const x of [-10, 10])
    for (const z of [-13, 13]) {
      const hole = cylinder(1.2, 0.4, x, 22, z, black);
      hole.rotation.set(0, 0, 0);
    }
  cylinder(10.4, 1, 0, 8, 20.8, black);
  rotor = new THREE.Group();
  rotor.position.set(0, 8, 22);
  scene.add(rotor);
  cylinder(9.8, 1.8, 0, 0, 0, metal, rotor);
  cylinder(3.9, 1.1, 0, 0, 1.2, metal, rotor);
  cylinder(2.0, 0.25, 0, 0, 1.83, black, rotor);
  // Subtle concentric machining lines on the metal face.
  for (const radius of [3.6, 9.4]) {
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(radius, 0.07, 6, 80),
      edge,
    );
    ring.position.z = radius < 4 ? 1.79 : 0.94;
    rotor.add(ring);
  }
  for (let i = 0; i < 6; i++) {
    const a = (i * Math.PI) / 3;
    const x = 6.8 * Math.sin(a),
      y = 6.8 * Math.cos(a);
    cylinder(0.92, 0.22, x, y, 0.98, black, rotor);
    const rim = new THREE.Mesh(
      new THREE.TorusGeometry(0.94, 0.08, 6, 24),
      dark,
    );
    rim.position.set(x, y, 1.1);
    rotor.add(rim);
  }
  // Small shaft index keeps direction legible without changing the reference silhouette.
  const marker = new THREE.Mesh(new THREE.BoxGeometry(1.2, 2, 0.15), teal);
  marker.position.set(0, -8.4, 1.03);
  rotor.add(marker);
  scene.updateMatrixWorld(true);
  modelBounds = new THREE.Box3().setFromObject(scene);
  scene.add(new THREE.HemisphereLight(0xffffff, 0x66666b, 2.7));
  const key = new THREE.DirectionalLight(0xffffff, 3);
  key.position.set(35, 70, 90);
  scene.add(key);
  const rim = new THREE.DirectionalLight(0xdde4ed, 2);
  rim.position.set(-40, 10, -30);
  scene.add(rim);
  observer = new ResizeObserver(resize);
  observer.observe(host.value!);
  resize();
  if (renderer) renderer.setAnimationLoop(tick);
  else {
    // Still show a transparent, data-driven shaft on devices without WebGL.
    const animate = (now: number) => {
      if (disposed) return;
      tick(now);
      requestAnimationFrame(animate);
    };
    requestAnimationFrame(animate);
  }
});
onBeforeUnmount(() => {
  disposed = true;
  observer?.disconnect();
  renderer?.setAnimationLoop(null);
  scene?.traverse((obj) => {
    if (obj instanceof THREE.Mesh) {
      obj.geometry.dispose();
      const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
      mats.forEach((m) => m.dispose());
    }
  });
  renderer?.dispose();
  renderer?.domElement.remove();
});
</script>
<template>
  <div
    ref="host"
    class="motor-model"
    role="img"
    :aria-label="
      model + ' 3D 모터 · 출력축 ' + shaftDegrees(shownAngle).toFixed(0) + '도'
    "
    :data-ready="ready || fallback"
    :data-angle="shownAngle"
    :data-target-angle="target"
    :data-origin="origin"
    :data-context="context"
  >
    <svg
      v-if="fallback"
      viewBox="-45 -55 90 110"
      class="motor-model-fallback"
      aria-hidden="true"
    >
      <path
        d="M-22-39 16-39 31-27 31 38 16 46-22 46Z"
        fill="#344352"
        stroke="#718394"
      />
      <rect
        x="-22"
        y="-39"
        width="38"
        height="85"
        rx="4"
        fill="#202d3b"
        stroke="#526779"
      />
      <g
        :transform="
          'translate(-3 -10) rotate(' + (-shownAngle * 180) / Math.PI + ')'
        "
      >
        <circle r="17" fill="#a0afbd" stroke="#d1dce4" />
        <circle r="5" fill="#bfc0be" stroke="#242527" />
        <circle r="2.5" fill="#090a0b" />
        <circle
          v-for="i in 6"
          :key="i"
          :cx="12 * Math.sin((i * Math.PI) / 3)"
          :cy="12 * Math.cos((i * Math.PI) / 3)"
          r="1.3"
          fill="#090a0b"
        />
        <path d="M0 9V15" stroke="#69dfbf" stroke-width="4" />
      </g>
    </svg>
  </div>
</template>
<style scoped>
.motor-model {
  position: absolute;
  inset: 0;
  min-width: 0;
}
.motor-model :deep(canvas) {
  display: block;
  width: 100%;
  height: 100%;
}
.motor-model-fallback {
  display: block;
  width: 100%;
  height: 100%;
  max-height: 370px;
}
</style>
