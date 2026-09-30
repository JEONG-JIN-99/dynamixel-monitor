import type { Sample } from "../types/motor";
import { diagnosisView } from "./overview";
export interface MotorObservation {
  power: "on" | "off" | "unknown";
  moving: boolean | null;
}
export function fleetStatus(
  observation: MotorObservation | undefined,
  sample: Sample | null,
  available: boolean,
) {
  const power = available ? (observation?.power ?? "unknown") : "unknown";
  if (power !== "on")
    return {
      power,
      moving: null,
      tone: power === "off" ? "off" : "unknown",
      diagnosis: power === "off" ? "전원 꺼짐" : "상태 미확인",
      diagnosisTone: "muted",
      powerLabel: power === "off" ? "꺼짐" : "미확인",
      movement: "—",
    };
  const moving = sample?.moving ?? observation?.moving ?? null;
  const result = diagnosisView(sample),
    hardwareError = !!sample?.hwError;
  const fault = result.state === "fault" || hardwareError;
  return {
    power,
    moving,
    tone: fault
      ? "fault"
      : result.state === "normal" && moving === false
        ? "idle"
        : result.state === "normal" && moving
          ? "running"
          : "unknown",
    diagnosis:
      hardwareError && result.state !== "fault"
        ? "하드웨어 오류"
        : result.label,
    diagnosisTone: fault
      ? "fault"
      : result.state === "normal"
        ? "normal"
        : "muted",
    powerLabel: "켜짐",
    movement: moving == null ? "동작 미확인" : moving ? "동작중" : "멈춤",
  };
}
