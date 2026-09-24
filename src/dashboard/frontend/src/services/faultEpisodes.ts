import type { AnalysisPoint } from "../types/analysis";
import { diagnosisView, diagnosisLabels } from "./overview";
export interface FaultEpisode {
  id: string;
  code: string;
  label: string;
  startMs: number;
  lastMs: number;
  endMs: number | null;
  leftBoundary: "known" | "window" | "gap";
  ending: "resolved" | "ongoing" | "unconfirmed";
  startTimestamp: number | null;
  endTimestamp: number | null;
}
// Only confirmed adjacent observations can establish continuity or recovery.
export function faultEpisodes(
  points: readonly AnalysisPoint[],
  intervalMs: number,
  live: boolean,
): FaultEpisode[] {
  const result: FaultEpisode[] = [],
    open = new Map<string, FaultEpisode>();
  let previous: AnalysisPoint | undefined,
    previousKnown = false;
  for (const point of points) {
    const state = diagnosisView(point),
      known = state.state !== "waiting";
    const gap =
      !!previous &&
      point.elapsedMs - previous.elapsedMs > Math.max(1, intervalMs) * 2.5;
    if (gap || !known) {
      open.clear();
    }
    if (known) {
      const codes = new Set(state.state === "fault" ? state.codes : []);
      for (const [code, item] of open) {
        if (!codes.has(code)) {
          item.endMs = point.elapsedMs;
          item.endTimestamp = point.timestamp ?? null;
          item.ending = "resolved";
          open.delete(code);
        }
      }
      for (const code of codes) {
        let item = open.get(code);
        if (!item) {
          item = {
            id: `${point.elapsedMs}:${code}`,
            code,
            label:
              diagnosisLabels[code as keyof typeof diagnosisLabels] ??
              "미분류 이상",
            startMs: point.elapsedMs,
            lastMs: point.elapsedMs,
            endMs: null,
            startTimestamp: point.timestamp ?? null,
            endTimestamp: null,
            leftBoundary: !previous
              ? point.elapsedMs === 0
                ? "known"
                : "window"
              : gap || !previousKnown
                ? "gap"
                : "known",
            ending: "unconfirmed",
          };
          open.set(code, item);
          result.push(item);
        }
        item.lastMs = point.elapsedMs;
      }
    }
    previous = point;
    previousKnown = known;
  }
  if (live) for (const item of open.values()) item.ending = "ongoing";
  return result.sort(
    (a, b) => b.startMs - a.startMs || a.code.localeCompare(b.code),
  );
}
