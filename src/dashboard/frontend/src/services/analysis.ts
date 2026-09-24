import { controlTable, supportedModels } from "./controlTable";
import { diagnosisView } from "./overview";
import type {
  AnalysisInput,
  AnalysisPoint,
  PlotKey,
  TimeSegment,
} from "../types/analysis";
import type { MotorMetadata, RegisterReading, Sample } from "../types/motor";
const definitions = new Map(controlTable.map((d) => [d.address, d]));
const finite = (v: unknown): v is number =>
  typeof v === "number" && Number.isFinite(v);
export function rawNumber(
  address: number,
  reading?: RegisterReading,
): number | null {
  const d = definitions.get(address);
  if (
    !d ||
    reading?.status !== "received" ||
    !finite(reading.raw) ||
    !Number.isInteger(reading.raw) ||
    reading.raw < (d.signed ? -(2 ** (d.size * 8 - 1)) : 0) ||
    reading.raw >= 2 ** (d.size * 8)
  )
    return null;
  return d.signed && reading.raw >= 2 ** (d.size * 8 - 1)
    ? reading.raw - 2 ** (d.size * 8)
    : reading.raw;
}
export function analysisPoint(
  input: AnalysisInput,
  metadata?: Pick<MotorMetadata, "registers">,
): AnalysisPoint {
  const sample = input as Partial<Sample>;
  const supported = supportedModels.includes(input.model);
  const read = (
    address: number,
    fallback?: keyof Sample,
    scale = 1,
  ): number | null => {
    const r = input.registers?.[address];
    if (r) {
      const n = supported ? rawNumber(address, r) : null;
      return n == null ? null : n * scale;
    }
    const v = fallback ? sample[fallback] : null;
    return supported && finite(v)
      ? v
      : supported && typeof v === "boolean"
        ? Number(v)
        : null;
  };
  const config = (address: number) => {
    const a = input.registers?.[address],
      b = metadata?.registers?.[address];
    const time = sample.receivedAt ?? input.timestamp;
    const eligible = b && b.receivedAt <= (time ?? -Infinity) ? b : undefined;
    return supported ? rawNumber(address, a ?? eligible) : null;
  };
  const mode = config(11);
  const positionMode = mode != null && [3, 4, 5].includes(mode);
  const velocityMode = positionMode || mode === 1;
  const point: AnalysisPoint = {
    elapsedMs: input.elapsedMs,
    timestamp: finite(input.timestamp) ? input.timestamp : null,
    diagnosis: input.diagnosis,
    current: read(126, "current", 0.00269),
    pwm: read(124, "pwm", 0.113),
    velocity: read(128, "velocity", 0.229),
    position: read(132, "position"),
    velocityTrajectory:
      mode != null && !velocityMode
        ? null
        : read(136, "velocityTrajectory", 0.229),
    positionTrajectory:
      mode != null && !positionMode ? null : read(140, "positionTrajectory"),
    goalPosition:
      mode != null && !positionMode ? null : read(116, "goalPosition"),
    voltage: read(144, "voltage", 0.1),
    temperature: read(146, "temperature"),
    torque: read(64),
    movingFlag: read(122, "moving"),
    profile: null,
    inPosition: null,
    followingError: null,
    hardwareError: read(70, "hwError"),
    operatingMode: mode,
    positionError: null,
    velocityError: null,
    limits: {},
  };
  for (const [key, address, scale, symmetric] of [
    ["current", 38, 0.00269, true],
    ["pwm", 36, 0.113, true],
    ["voltage", 32, 0.1, false],
    ["temperature", 31, 1, false],
  ] as const) {
    const raw = config(address);
    if (raw != null)
      point.limits[key] = [
        { value: raw * scale, label: "설정 상한" },
        ...(symmetric ? [{ value: -raw * scale, label: "설정 하한" }] : []),
      ];
  }
  const minVoltage = config(34);
  if (minVoltage != null)
    point.limits.voltage = [
      ...(point.limits.voltage ?? []),
      { value: minVoltage * 0.1, label: "설정 하한" },
    ];
  const moving = read(123, "movingStatus");
  if (moving != null) {
    point.profile = moving & 2 ? 1 : 0;
    if (positionMode) {
      point.inPosition = moving & 1 ? 1 : 0;
      point.followingError = moving & 8 ? 1 : 0;
    }
  }
  // Never combine a cached register with a fresh one, or raw and converted sources.
  const aligned = (a: number, b: number) => {
    const x = input.registers?.[a],
      y = input.registers?.[b];
    return (
      (!x && !y) ||
      (!!x && !!y && finite(x.receivedAt) && x.receivedAt === y.receivedAt)
    );
  };
  if (
    positionMode &&
    aligned(132, 140) &&
    finite(point.position) &&
    finite(point.positionTrajectory)
  )
    point.positionError = point.position - point.positionTrajectory;
  if (
    velocityMode &&
    aligned(128, 136) &&
    finite(point.velocity) &&
    finite(point.velocityTrajectory)
  )
    point.velocityError = point.velocity - point.velocityTrajectory;
  return point;
}
export function analysisHistory(
  inputs: AnalysisInput[],
  metadata?: Pick<MotorMetadata, "registers">,
): AnalysisPoint[] {
  // Carry forward only configuration readings, never live measurements.
  let registers = { ...metadata?.registers };
  return inputs.map((input) => {
    const point = analysisPoint(input, {
      ...metadata,
      registers,
    } as Pick<MotorMetadata, "registers">);
    for (const address of [11, 31, 32, 34, 36, 38]) {
      const reading = input.registers?.[address];
      if (reading) registers[address] = reading;
    }
    return point;
  });
}
export function plotHistory(
  points: AnalysisPoint[],
  intervalMs: number,
): AnalysisPoint[] {
  const result: AnalysisPoint[] = [];
  for (const point of points) {
    const previous = result.at(-1);
    if (previous && point.elapsedMs - previous.elapsedMs > intervalMs * 2.5) {
      const gap = { ...point, elapsedMs: previous.elapsedMs + intervalMs };
      for (const key of [
        "current",
        "pwm",
        "velocity",
        "position",
        "velocityTrajectory",
        "positionTrajectory",
        "goalPosition",
        "voltage",
        "temperature",
        "positionError",
        "velocityError",
      ] as PlotKey[])
        gap[key] = null;
      result.push(gap);
    }
    result.push(point);
  }
  return result;
}
export const timelineRows = [
  { key: "diagnosis", label: "알고리즘 판정" },
  { key: "torque", label: "토크 활성" },
  { key: "movingFlag", label: "이동 플래그" },
  { key: "profile", label: "프로파일 진행" },
  { key: "inPosition", label: "목표 위치 도달" },
  { key: "followingError", label: "추종 오류 비트" },
  { key: "hardwareError", label: "하드웨어 오류" },
] as const;
export type TimelineKey = (typeof timelineRows)[number]["key"];
export function hardwareLabel(value: number): string {
  if (value === 0) return "오류 없음";
  const bits: [number, string][] = [
    [1, "입력 전압 오류"],
    [4, "과열"],
    [8, "엔코더 오류"],
    [16, "전기 충격 오류"],
    [32, "과부하"],
  ];
  const labels = bits.filter(([bit]) => value & bit).map(([, label]) => label);
  if (value & ~61) labels.push(`미정의 비트 (0x${value.toString(16)})`);
  return labels.join(" · ");
}
export function stateAt(
  point: AnalysisPoint,
  key: TimelineKey,
): Pick<TimeSegment, "label" | "tone"> {
  if (key === "diagnosis") {
    const d = diagnosisView(point);
    return {
      label: d.label,
      tone:
        d.state === "fault"
          ? "fault"
          : d.state === "normal"
            ? "active"
            : "unknown",
    };
  }
  const value = point[key];
  if (value == null) return { label: "미수신 / 모드 확인", tone: "unknown" };
  if (key === "hardwareError")
    return { label: hardwareLabel(value), tone: value ? "fault" : "idle" };
  if (key === "followingError")
    return {
      label: value ? "추종 오류" : "오류 없음",
      tone: value ? "fault" : "idle",
    };
  return { label: key === "inPosition" ? (value ? "도달" : "미도달") : key === "profile" ? (value ? "진행 중" : "완료") : value ? "켜짐" : "꺼짐", tone: value ? "active" : "idle" };
}
export function timeSegments(
  points: AnalysisPoint[],
  key: TimelineKey,
  intervalMs: number,
): TimeSegment[] {
  const result: TimeSegment[] = [];
  for (let i = 0; i < points.length; i++) {
    const p = points[i]!,
      next = points[i + 1];
    const start = p.elapsedMs / 1000;
    // End at the latest observation; never project an old status into the future.
    const end = next
      ? Math.min(next.elapsedMs, p.elapsedMs + intervalMs * 1.5) / 1000
      : start;
    if (end <= start) continue;
    const state = stateAt(p, key),
      previous = result.at(-1);
    if (
      previous &&
      previous.end === start &&
      previous.label === state.label &&
      previous.tone === state.tone
    )
      previous.end = end;
    else result.push({ start, end, ...state });
  }
  return result;
}
