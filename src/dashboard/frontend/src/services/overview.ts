import type { Sample } from "../types/motor";
export const SCREEN_INTERVAL_MS = 100;
export const diagnosisLabels = {
  overvoltage: "과전압",
  undervoltage: "과소전압",
  overload: "과부하",
  undercurrent: "과소전류",
  friction: "마찰",
  gear_backlash: "기어 백래시",
} as const;
export function motorKey(motor: { model: string; id: number }) {
  return `${motor.model}:${motor.id}`;
}
export function diagnosisView(sample: Pick<Sample, "diagnosis"> | null) {
  const result = sample?.diagnosis;
  if (!result || result.state === "waiting")
    return { state: "waiting", label: "판정 대기", codes: [] as string[] };
  if (result.state === "normal" && result.codes.length === 0)
    return { state: "normal", label: "정상", codes: [] as string[] };
  if (result.state !== "fault" || result.codes.length === 0)
    return { state: "waiting", label: "판정 확인 필요", codes: [] as string[] };
  return {
    state: "fault",
    label: result.codes
      .map(
        (code) =>
          diagnosisLabels[code as keyof typeof diagnosisLabels] ??
          "미분류 이상",
      )
      .join(" · "),
    codes: result.codes,
  };
}
export function formatValue(value: unknown, decimals = 0) {
  return typeof value === "number" && Number.isFinite(value)
    ? value.toLocaleString("ko-KR", {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      })
    : "—";
}
