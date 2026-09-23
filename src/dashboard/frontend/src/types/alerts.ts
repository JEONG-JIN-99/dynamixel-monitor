import type { SourceMode } from "./motor";

export interface DiagnosisAlert {
  id: string;
  context: string;
  source: SourceMode;
  model: string;
  motorId: number;
  busId: string;
  runId: string;
  code: string;
  startedAt: number;
  lastSeenAt: number;
  resolvedAt: number | null;
  read: boolean;
}

export interface AlertCursor {
  seq: number;
  elapsedMs: number;
  known: boolean;
}

export interface AlertJournal {
  version: 1;
  records: DiagnosisAlert[];
  cursors: Record<string, AlertCursor>;
}
