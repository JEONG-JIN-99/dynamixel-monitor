import type { Sample, SourceMode } from "../types/motor";
import type { AlertJournal, DiagnosisAlert } from "../types/alerts";
import { diagnosisLabels } from "./overview";

export const ALERT_STORAGE_KEY = "motor-dashboard.diagnosis-alerts.v1";
export const emptyJournal = (): AlertJournal => ({
  version: 1,
  records: [],
  cursors: {},
});
export function alertSession(
  source: SourceMode,
  server: string,
  session: string | null,
  run: string | null,
) {
  return JSON.stringify([source, server, session, run]);
}
export function alertContext(source: SourceMode, sample: Sample) {
  return JSON.stringify([
    alertSession(
      source,
      sample.serverSessionId,
      sample.sourceSessionId,
      sample.runId,
    ),
    sample.busId ?? "",
    sample.model,
    sample.id,
  ]);
}
export function alertLabel(code: string): string {
  return (
    diagnosisLabels[code as keyof typeof diagnosisLabels] ??
    "미분류 이상 (" + code + ")"
  );
}
const finite = (n: unknown): n is number =>
  typeof n === "number" && Number.isFinite(n);

// Each codes array is the COMPLETE current set for one motor, not a delta.
// Process every sample before the chart's 60-second retention trims history.
export function ingestAlerts(
  journal: AlertJournal,
  source: SourceMode,
  samples: Sample[],
  read = false,
): boolean {
  let changed = false;
  for (const sample of [...samples].sort((a, b) => a.seq - b.seq)) {
    const at = finite(sample.timestamp) ? sample.timestamp : sample.receivedAt;
    if (
      !finite(at) ||
      !finite(sample.seq) ||
      !finite(sample.elapsedMs) ||
      !finite(sample.id) ||
      typeof sample.model !== "string"
    )
      continue;
    const context = alertContext(source, sample);
    const previous = journal.cursors[context];
    if (
      previous &&
      (sample.seq <= previous.seq || sample.elapsedMs < previous.elapsedMs)
    )
      continue;
    const diagnosis = sample.diagnosis;
    const codesValid =
      Array.isArray(diagnosis?.codes) &&
      diagnosis.codes.every(
        (c) => typeof c === "string" && c.trim().length > 0,
      );
    const known =
      !!diagnosis &&
      codesValid &&
      ((diagnosis.state === "normal" && diagnosis.codes.length === 0) ||
        (diagnosis.state === "fault" && diagnosis.codes.length > 0));
    journal.cursors[context] = {
      seq: sample.seq,
      elapsedMs: sample.elapsedMs,
      known,
    };
    changed = true;
    // Missing, waiting or malformed results must never clear a fault.
    if (!known) continue;
    const codes = new Set(diagnosis!.codes);
    const open = journal.records.filter(
      (r) => r.context === context && r.resolvedAt === null,
    );
    for (const record of open) {
      if (codes.has(record.code)) record.lastSeenAt = at;
      else record.resolvedAt = at;
    }
    for (const code of codes) {
      if (open.some((r) => r.code === code)) continue;
      journal.records.push({
        id: JSON.stringify([context, sample.seq, code]),
        context,
        source,
        model: sample.model,
        motorId: sample.id,
        busId: sample.busId ?? "",
        runId: sample.runId,
        code,
        startedAt: at,
        lastSeenAt: at,
        resolvedAt: null,
        read,
      });
    }
  }
  return changed;
}

export function alertStatus(
  journal: AlertJournal,
  record: DiagnosisAlert,
  session: string | null,
  available: boolean,
): "active" | "resolved" | "unknown" {
  if (record.resolvedAt !== null) return "resolved";
  return available &&
    session === JSON.parse(record.context)[0] &&
    journal.cursors[record.context]?.known
    ? "active"
    : "unknown";
}

export function restoreJournal(raw: string | null): AlertJournal {
  if (!raw) return emptyJournal();
  const value = JSON.parse(raw) as AlertJournal;
  if (
    value?.version !== 1 ||
    !Array.isArray(value.records) ||
    !value.cursors ||
    typeof value.cursors !== "object" ||
    Array.isArray(value.cursors)
  )
    throw new Error("Invalid alert storage");
  for (const r of value.records) {
    if (
      !r ||
      ![r.id, r.context, r.model, r.busId, r.runId, r.code].every(
        (v) => typeof v === "string",
      ) ||
      !["csv", "mock"].includes(r.source) ||
      ![r.motorId, r.startedAt, r.lastSeenAt].every(finite) ||
      !(r.resolvedAt === null || finite(r.resolvedAt)) ||
      typeof r.read !== "boolean"
    )
      throw new Error("Invalid alert record");
    const context = JSON.parse(r.context);
    if (
      !Array.isArray(context) ||
      context.length !== 4 ||
      typeof context[0] !== "string"
    )
      throw new Error("Invalid alert context");
  }
  for (const c of Object.values(value.cursors)) {
    if (
      !c ||
      !finite(c.seq) ||
      !finite(c.elapsedMs) ||
      typeof c.known !== "boolean"
    )
      throw new Error("Invalid alert cursor");
  }
  return value;
}
