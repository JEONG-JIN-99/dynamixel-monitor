import type { DiagnosisResult, RegisterReading, Sample } from "./motor";

// Transport-independent input. A backend only needs readings, identity and acquisition time.
export interface MotorFrame {
  id: number;
  model: string;
  elapsedMs: number;
  timestamp: number;
  registers: Record<string, RegisterReading>;
  diagnosis?: DiagnosisResult | null;
}
export type PlotKey =
  | "current"
  | "velocity"
  | "velocityTrajectory"
  | "position"
  | "positionTrajectory"
  | "goalPosition"
  | "pwm"
  | "voltage"
  | "temperature"
  | "positionError"
  | "velocityError";
export type PlotPoint = { elapsedMs: number; timestamp?: number | null } & Partial<
  Record<PlotKey, number | null>
>;
export interface PlotField {
  key: PlotKey;
  label: string;
  color: string;
  dashed?: boolean;
  dotted?: boolean;
}
export interface ReferenceLine {
  value: number;
  label: string;
}
export interface AnalysisPoint extends PlotPoint {
  diagnosis?: DiagnosisResult | null;
  torque: number | null;
  movingFlag: number | null;
  profile: number | null;
  inPosition: number | null;
  followingError: number | null;
  hardwareError: number | null;
  operatingMode: number | null;
  limits: Partial<Record<PlotKey, ReferenceLine[]>>;
}
export type AnalysisInput = MotorFrame | Sample;
export interface TimeSegment {
  start: number;
  end: number;
  label: string;
  tone: "active" | "idle" | "fault" | "unknown";
}
