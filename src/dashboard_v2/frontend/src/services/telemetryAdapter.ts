import type { Message, RegisterSample, Sample } from "../types/motor";
import { analysisPoint, rawNumber } from "./analysis";

// Shared transport boundary: real and simulated backends use the same conversion.
// This only decodes received readings. It never generates measurements or verdicts.
export function normalizeSample(input: Sample | RegisterSample): Sample {
  if (!input.registers) return input as Sample;
  const previous = input as Partial<Sample>;
  const point = analysisPoint(input);
  const tick = input.registers[120]
    ? rawNumber(120, input.registers[120])
    : (previous.realtimeTick ?? null);
  return {
    ...input,
    pcTime: previous.pcTime ?? "",
    status: previous.status ?? null,
    hwError: point.hardwareError,
    moving: point.movingFlag == null ? null : !!point.movingFlag,
    movingStatus: input.registers[123]
      ? rawNumber(123, input.registers[123])
      : (previous.movingStatus ?? null),
    realtimeTick: tick,
    current: point.current ?? null,
    pwm: point.pwm ?? null,
    position: point.position ?? null,
    velocity: point.velocity ?? null,
    positionTrajectory: point.positionTrajectory ?? null,
    velocityTrajectory: point.velocityTrajectory ?? null,
    goalPosition: point.goalPosition ?? null,
    goalSource: input.registers[116] ? null : (previous.goalSource ?? null),
    voltage: point.voltage ?? null,
    temperature: point.temperature ?? null,
    loadPercent: previous.loadPercent ?? null,
    cycle: previous.cycle ?? null,
    phase: previous.phase ?? null,
    condition: previous.condition ?? null,
  };
}
export function normalizeMessage(
  message: Message<Sample | RegisterSample>,
): Message {
  if (message.type === "snapshot" || message.type === "reset")
    return {
      ...message,
      history: message.history.map(normalizeSample),
      latest: message.latest ? normalizeSample(message.latest) : null,
    };
  if (message.type === "samples")
    return { ...message, samples: message.samples.map(normalizeSample) };
  return message;
}
