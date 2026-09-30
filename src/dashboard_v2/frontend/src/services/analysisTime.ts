export type TimeMode = "elapsed" | "clock";
const pad = (value: number) => String(value).padStart(2, "0");
export function elapsedTime(seconds: number, precise = false): string {
  if (!Number.isFinite(seconds)) return "—";
  const ms = Math.max(0, Math.round(seconds * 1000)),
    whole = Math.floor(ms / 1000);
  const days = Math.floor(whole / 86400),
    hours = Math.floor(whole / 3600) % 24,
    minutes = Math.floor(whole / 60) % 60;
  const fraction =
    precise && ms % 1000
      ? "." +
        String(ms % 1000)
          .padStart(3, "0")
          .replace(/0+$/, "")
      : "";
  const clock =
    whole >= 3600
      ? `${pad(hours)}:${pad(minutes)}:${pad(whole % 60)}`
      : `${Math.floor(whole / 60)}:${pad(whole % 60)}`;
  return `${days ? `${days}일 ` : ""}${clock}${fraction}`;
}
const dateFormat = new Intl.DateTimeFormat("sv-SE", {
  timeZone: "Asia/Seoul",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false,
});
export function clockTime(
  timestamp: number | null,
  includeDate = false,
  precise = false,
): string {
  if (
    timestamp == null ||
    !Number.isFinite(timestamp) ||
    Math.abs(timestamp) > 8.64e15
  )
    return "시각 미수신";
  const text = dateFormat.format(new Date(timestamp)),
    ms = ((Math.round(timestamp) % 1000) + 1000) % 1000;
  return (
    (includeDate ? text : text.slice(-8)) +
    (precise && ms ? "." + String(ms).padStart(3, "0").replace(/0+$/, "") : "")
  );
}
export function timeOrigin(
  points: readonly { elapsedMs: number; timestamp?: number | null }[],
): number | null {
  const point = points.find(
    (p) =>
      typeof p.timestamp === "number" &&
      Number.isFinite(p.timestamp) &&
      Math.abs(p.timestamp) < 8.64e15,
  );
  return point?.timestamp == null ? null : point.timestamp - point.elapsedMs;
}
export function durationText(ms: number): string {
  const seconds = Math.max(0, ms) / 1000;
  return seconds < 60
    ? `${Number(seconds.toFixed(3))}초`
    : elapsedTime(seconds, true);
}
