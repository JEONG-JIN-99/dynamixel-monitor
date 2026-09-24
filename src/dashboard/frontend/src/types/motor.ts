export type SourceMode = "csv" | "mock";
export type ConnectionState = "connecting" | "connected" | "disconnected";
// Optional algorithm output, independent of experiment condition and hardware error bits.
export interface DiagnosisResult {
  state: "waiting" | "normal" | "fault";
  codes: string[];
}
// A real register read. Optional so existing CSV messages remain compatible.
export interface RegisterReading {
  raw: number | null;
  receivedAt: number; // Unix milliseconds at acquisition
  status: "received" | "unsupported" | "error";
  error?: string;
}
export interface Sample {
  basePosition?: number | null;
  registers?: Record<string, RegisterReading>;
  diagnosis?: DiagnosisResult | null;
  serverSessionId: string;
  sourceSessionId: string;
  runId: string;
  busId: string;
  seq: number;
  id: number;
  model: string;
  elapsedMs: number;
  timestamp: number | null;
  receivedAt: number;
  pcTime: string;
  status: "normal" | "critical" | null;
  hwError: number | null;
  moving: boolean | null;
  movingStatus: number | null;
  realtimeTick: number | null;
  pwm: number | null;
  current: number | null;
  loadPercent: number | null;
  velocity: number | null;
  position: number | null;
  velocityTrajectory: number | null;
  positionTrajectory: number | null;
  goalPosition: number | null;
  goalSource: "command" | null;
  voltage: number | null;
  temperature: number | null;
  cycle: number | null;
  phase: string | null;
  condition: string | null;
}
export interface Experiment {
  runId: string;
  status: string;
  csvPath: string | null;
  metadataPath: string | null;
  motorModel: string;
  motorId: number;
  sampleIntervalSec: number;
  flushEveryRows: number;
  startedAt: string;
  endedAt: string | null;
  error: string | null;
}
export interface MotorMetadata {
  registers?: Record<string, RegisterReading>;
  simulated?: boolean;
  id: number;
  model: string;
  modelNumber: number | null;
  firmware: number | null;
  settings: Record<string, string | number | boolean>;
  source: string;
  limits: {
    current: number | null;
    temperature: number | null;
    voltageMin: number | null;
    voltageMax: number | null;
  };
}
export interface SystemState {
  sourceMode: SourceMode;
  validity: "waiting" | "valid" | "stale" | "error";
  experimentStatus: string;
  dataAgeSec: number | null;
  configuredHz: number | null;
  observedHz: number | null;
  expectedFlushSec: number | null;
  error: string | null;
  readerCaughtUp: boolean;
  writerActive?: boolean | null;
}
export interface LogEvent {
  id: string;
  time: string;
  severity: string;
  message: string;
}
// Wire samples can contain just raw registers, identity, timing and diagnosis.
export type RegisterSample = Pick<
  Sample,
  | "serverSessionId"
  | "sourceSessionId"
  | "runId"
  | "busId"
  | "seq"
  | "id"
  | "model"
  | "elapsedMs"
  | "receivedAt"
  | "diagnosis"
> & {
  timestamp: number;
  basePosition?: number | null;
  registers: Record<string, RegisterReading>;
};
export interface Snapshot<T = Sample> {
  serverSessionId: string;
  sourceSessionId: string | null;
  runId: string | null;
  experiment: Experiment | null;
  metadata: MotorMetadata[];
  latest: T | null;
  history: T[];
  retentionSec: number;
  capacity: number;
  seq: number;
  events: LogEvent[];
  system: SystemState;
}
export type Message<T = Sample> = {
  schemaVersion: number;
  serverSessionId: string;
  sourceSessionId: string | null;
} & (
  | ({ type: "snapshot" } & Snapshot<T>)
  | ({ type: "reset" } & Snapshot<T>)
  | { type: "samples"; samples: T[] }
  | {
      type: "system";
      system: SystemState;
      experiment: Experiment | null;
      metadata: MotorMetadata[];
    }
  | { type: "event"; event: LogEvent }
);
