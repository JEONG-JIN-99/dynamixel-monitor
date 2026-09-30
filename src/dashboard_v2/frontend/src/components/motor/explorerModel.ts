import * as THREE from "three";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import type { MotorSlot } from "../../services/motorSlot";

export interface ExplorerJoint {
  slot: MotorSlot;
  anchor: THREE.Vector3;
  material: THREE.MeshStandardMaterial;
  ring: THREE.Mesh;
}

// Cross-sections produce tapered, bevelled armor rather than rectangular limbs.
type Section = [z: number, width: number, height: number, centerY: number];
function armorGeometry(sections: Section[]) {
  const vertices: number[] = [], indices: number[] = [];
  for (const [z, w, h, y] of sections) {
    for (const [x, dy] of [[-.35, .5], [.35, .5], [.5, .28], [.5, -.28], [.35, -.5], [-.35, -.5], [-.5, -.28], [-.5, .28]]) {
      vertices.push(x! * w, y + dy! * h, z);
    }
  }
  for (let r = 0; r < sections.length - 1; r++) {
    for (let p = 0; p < 8; p++) {
      const a = r * 8 + p, b = r * 8 + (p + 1) % 8;
      indices.push(a, a + 8, b, b, a + 8, b + 8);
    }
  }
  for (let p = 1; p < 7; p++) {
    indices.push(0, p, p + 1);
    const last = (sections.length - 1) * 8;
    indices.push(last, last + p + 1, last + p);
  }
  const indexed = new THREE.BufferGeometry();
  indexed.setAttribute("position", new THREE.Float32BufferAttribute(vertices, 3));
  indexed.setIndex(indices);
  const geometry = indexed.toNonIndexed();
  indexed.dispose();
  geometry.computeVertexNormals();
  return geometry;
}

export function buildExplorerModel(scene: THREE.Scene): ExplorerJoint[] {
  const joints: ExplorerJoint[] = [];
  const shell = new THREE.MeshStandardMaterial({ color: 0xe9edf0, roughness: .36, metalness: .24 });
  const ceramic = new THREE.MeshStandardMaterial({ color: 0xf7f6ed, roughness: .4, metalness: .12 });
  const alloy = new THREE.MeshStandardMaterial({ color: 0x778490, roughness: .32, metalness: .72 });
  const frame = new THREE.MeshStandardMaterial({ color: 0x25303b, roughness: .43, metalness: .65 });
  const rubber = new THREE.MeshStandardMaterial({ color: 0x101924, roughness: .85 });
  const glass = new THREE.MeshStandardMaterial({ color: 0x081728, roughness: .15, metalness: .55 });
  const sensor = new THREE.MeshStandardMaterial({ color: 0x9cddff, emissive: 0x42b6ff, emissiveIntensity: 2.2, roughness: .2 });
  const edge = new THREE.LineBasicMaterial({ color: 0x4e6174, transparent: true, opacity: .18 });
  const selectedMaterial = new THREE.MeshBasicMaterial({ color: 0xbeeaff });

  function mesh(geometry: THREE.BufferGeometry, material: THREE.Material, at = new THREE.Vector3(), outlined = false) {
    const item = new THREE.Mesh(geometry, material);
    item.position.copy(at);
    item.castShadow = true;
    item.receiveShadow = true;
    if (outlined) item.add(new THREE.LineSegments(new THREE.EdgesGeometry(geometry, 28), edge));
    scene.add(item);
    return item;
  }
  function box(w: number, h: number, d: number, x: number, y: number, z: number, material: THREE.Material = shell) {
    return mesh(new RoundedBoxGeometry(w, h, d, 2, Math.min(.07, h / 4, d / 4)), material, new THREE.Vector3(x, y, z));
  }
  function armor(sections: Section[], material: THREE.Material = shell) {
    return mesh(armorGeometry(sections), material, undefined, true);
  }
  function cylinder(radius: number, depth: number, at: THREE.Vector3, material: THREE.Material, axis: "x" | "z" = "x") {
    const item = mesh(new THREE.CylinderGeometry(radius, radius, depth, 40), material, at);
    if (axis === "x") item.rotation.z = Math.PI / 2;
    else item.rotation.x = Math.PI / 2;
    return item;
  }
  function ring(radius: number, thickness: number, at: THREE.Vector3, material: THREE.Material) {
    const item = mesh(new THREE.TorusGeometry(radius, thickness, 8, 48), material, at);
    item.rotation.y = Math.PI / 2;
    return item;
  }

  // Recessed chassis stays visible in the gaps between independent shell plates.
  armor([[-2.05, 1.25, .6, 2.84], [-1.65, 1.85, .8, 2.84], [1.45, 1.85, .8, 2.84], [2.24, 1.1, .45, 2.87]], frame);
  armor([[-1.98, 1.22, .42, 3.0], [-1.72, 1.74, .7, 3.0], [-.91, 1.76, .7, 3.0]], ceramic);
  armor([[-.86, 1.76, .7, 3.0], [.30, 1.76, .7, 3.0], [.68, 1.58, .64, 3.0]]);
  armor([[.74, 1.56, .62, 3.0], [1.43, 1.7, .62, 2.98], [2.15, 1.22, .43, 2.94]], ceramic);
  armor([[1.87, 1.4, .26, 2.63], [2.23, 1.05, .22, 2.74]], shell);
  // Narrow blue visor and dark top sensor panel identify the front.
  box(1.13, .19, .085, 0, 2.98, 2.24, glass);
  box(.98, .035, .036, 0, 3.01, 2.299, sensor);
  box(.65, .026, .42, 0, 3.326, 1.03, glass);
  box(.30, .025, .23, 0, 3.37, -.50, frame);
  for (const z of [-1.32, -.05]) {
    box(.85, .055, .30, 0, 3.37, z, frame);
    for (let i = 0; i < 5; i++) box(.035, .025, .21, -.29 + i * .145, 3.402, z, alloy);
  }
  for (const side of [-1, 1]) {
    const sidePanel = armor([[-.83, .13, .54, 2.77], [-.59, .16, .69, 2.77], [.57, .16, .69, 2.77], [.85, .1, .36, 2.8]], ceramic);
    sidePanel.position.x = side * .92;
    for (const z of [-.35, .08]) {
      box(.045, .11, .27, side * 1.015, 2.90, z, frame);
      box(.05, .025, .21, side * 1.04, 2.91, z, alloy);
    }
    // Small fasteners remain neutral: only the eight motor faces use status colors.
    for (const z of [-1.5, -.7, .52, 1.3]) cylinder(.025, .02, new THREE.Vector3(side * .82, 3.11, z), alloy);
  }

  function joint(slot: MotorSlot, at: THREE.Vector3, side: number) {
    cylinder(.385, .43, at, frame);
    cylinder(.405, .10, at.clone().add(new THREE.Vector3(side * .11, 0, 0)), shell);
    cylinder(.327, .10, at.clone().add(new THREE.Vector3(side * .24, 0, 0)), alloy);
    const center = at.clone().add(new THREE.Vector3(side * .305, 0, 0));
    cylinder(.28, .05, center, rubber);
    const material = new THREE.MeshStandardMaterial({ color: 0x89939e, emissive: 0x89939e, emissiveIntensity: .05, roughness: .35, metalness: .05, toneMapped: false });
    ring(.234, .045, center.clone().add(new THREE.Vector3(side * .045, 0, 0)), material);
    cylinder(.185, .022, center.clone().add(new THREE.Vector3(side * .031, 0, 0)), frame);
    const selectedRing = ring(.435, .014, center, selectedMaterial);
    joints.push({ slot, anchor: center.clone().add(new THREE.Vector3(side * .08, .48, 0)), material, ring: selectedRing });
    for (let i = 0; i < 6; i++) {
      const angle = i * Math.PI / 3;
      cylinder(.022, .025, center.clone().add(new THREE.Vector3(side * .01, Math.cos(angle) * .299, Math.sin(angle) * .299)), frame);
    }
  }
  function limb(a: THREE.Vector3, b: THREE.Vector3, width: number, depth: number) {
    const direction = b.clone().sub(a), length = direction.length();
    const rotation = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 0, 1), direction.normalize());
    const skeleton = box(width * .49, depth * .52, length, 0, 0, 0, frame);
    skeleton.position.copy(a).lerp(b, .5);
    skeleton.quaternion.copy(rotation);
    const plating = armor([[.22, width * .65, depth * .75, 0], [.39, width, depth, 0], [length - .29, width * .67, depth * .70, 0], [length - .19, width * .38, depth * .52, 0]], ceramic);
    plating.position.copy(a);
    plating.quaternion.copy(rotation);
    const inset = box(width * .30, .025, length * .30, 0, 0, 0, alloy);
    inset.position.copy(new THREE.Vector3(0, depth * .49, length * .51).applyQuaternion(rotation).add(a));
    inset.quaternion.copy(rotation);
  }
  for (const [index, side, fore] of [[0, -1, 1], [1, 1, 1], [2, -1, -1], [3, 1, -1]] as const) {
    const hip = new THREE.Vector3(side * 1.12, 2.76, fore * 1.46);
    const knee = new THREE.Vector3(side * 1.46, 1.46, fore * 1.94);
    const foot = new THREE.Vector3(side * 1.56, .22, fore * 1.37);
    cylinder(.28, .4, new THREE.Vector3(side * .94, hip.y, hip.z), alloy);
    limb(hip, knee, .58, .57);
    limb(knee, foot, .41, .43);
    const sole = armor([[-.29, .37, .13, .10], [-.18, .56, .18, .12], [.33, .52, .16, .11]], rubber);
    sole.position.set(foot.x, 0, foot.z);
    const toe = armor([[-.22, .28, .24, .27], [.08, .39, .30, .27], [.29, .40, .15, .23]], alloy);
    toe.position.set(foot.x, 0, foot.z);
    joint((index * 2 + 1) as MotorSlot, hip, side);
    joint((index * 2 + 2) as MotorSlot, knee, side);
  }
  const floor = mesh(new THREE.PlaneGeometry(200, 200), new THREE.MeshStandardMaterial({ color: 0x162333, roughness: .8 }), new THREE.Vector3(0, -.015, 0));
  floor.rotation.x = -Math.PI / 2;
  floor.castShadow = false;
  const grid = new THREE.GridHelper(12, 24, 0x31455b, 0x22354a);
  grid.position.y = -.01;
  scene.add(grid);
  return joints;
}
