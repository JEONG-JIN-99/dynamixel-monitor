import { expect, it } from "vitest";
import examples from "../../../contracts/examples.json";
import { controlTable } from "./controlTable";
import { normalizeMessage } from "./telemetryAdapter";
import type { Message, RegisterSample } from "../types/motor";

it("handoff wire examples match all 53 UI registers and use the real adapter", () => {
  const message = normalizeMessage(examples.snapshot as Message<RegisterSample>);
  if (message.type !== "snapshot") throw Error("Expected snapshot");
  expect(Object.keys(message.latest!.registers!).map(Number).sort((a,b)=>a-b))
    .toEqual(controlTable.map(r=>r.address).sort((a,b)=>a-b));
  expect(message.latest!.current).toBeCloseTo(examples.snapshot.latest.registers["126"].raw * .00269);
  expect(message.latest!.position).toBe(examples.snapshot.latest.registers["132"].raw);
  expect(message.latest!.diagnosis).toEqual({state:"normal", codes:[]});
  const batch = normalizeMessage(examples.samples as Message<RegisterSample>);
  if (batch.type !== "samples") throw Error("Expected samples");
  expect(batch.samples[0]!.seq).toBeGreaterThan(message.latest!.seq);
  expect(examples.history.samples.at(-1)).toEqual(examples.samples.samples[0]);
});
