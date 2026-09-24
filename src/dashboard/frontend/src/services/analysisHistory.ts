import type { AnalysisPoint } from "../types/analysis";
import type { Sample, RegisterSample } from "../types/motor";

export interface HistoryReply {
  schemaVersion: number;
  runId: string;
  serverSessionId: string;
  sourceSessionId: string;
  throughSeq: number;
  latestElapsedMs: number;
  samples: (Sample | RegisterSample)[];
}
export interface AnalysisRecord {
  seq: number;
  point: AnalysisPoint;
}
// Inputs from each transport are ordered; overlapping HTTP/WS prefixes are deduplicated.
export function appendRecords(
  previous: AnalysisRecord[],
  incoming: AnalysisRecord[],
  durationSec: number,
) {
  const next = previous.slice();
  let seq = next.at(-1)?.seq ?? -1;
  let elapsed = next.at(-1)?.point.elapsedMs ?? -1;
  for (const record of incoming) {
    if (record.seq <= seq || record.point.elapsedMs < elapsed) continue;
    next.push(record);
    seq = record.seq;
    elapsed = record.point.elapsedMs;
  }
  if (!durationSec) return next;
  const cutoff = elapsed - durationSec * 1000;
  let start = 0;
  while (start < next.length && next[start]!.point.elapsedMs < cutoff) start++;
  return start ? next.slice(start) : next;
}
