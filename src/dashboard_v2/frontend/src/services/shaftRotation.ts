export const PULSES_PER_TURN = 4096;
export function shaftAngle(position: number, origin: number): number {
  return ((position - origin) / PULSES_PER_TURN) * Math.PI * 2;
}
// Keep the full angle for interpolation: reducing 3 turns modulo 2π would lose the motion.
export function shaftDegrees(angle: number): number {
  return ((((angle * 180) / Math.PI) % 360) + 360) % 360;
}
