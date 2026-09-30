import { getCurrentInstance, inject, type InjectionKey } from "vue";
export const MOTOR_SLOTS = [1, 2, 3, 4, 5, 6, 7, 8] as const;
export type MotorSlot = (typeof MOTOR_SLOTS)[number];
export function parseMotorSlot(value: unknown): MotorSlot | null {
  return MOTOR_SLOTS.find((slot) => String(slot) === String(value)) ?? null;
}
export const motorSlotKey: InjectionKey<MotorSlot> = Symbol("motor-slot");
export function useMotorSlot(): MotorSlot {
  return getCurrentInstance() ? inject(motorSlotKey, 1) : 1;
}
export const motorUrl = (slot: MotorSlot, path: string) =>
  `/motors/${slot}${path}`;
export function useMotorFetch() {
  const slot = useMotorSlot();
  return (path: string, options?: RequestInit) =>
    fetch(motorUrl(slot, path), options);
}
