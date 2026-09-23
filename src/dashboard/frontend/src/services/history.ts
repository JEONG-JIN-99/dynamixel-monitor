import type { Sample } from "../types/motor";

// CSV seq can have holes after rejected records. Never fill gaps with invented values.
export function mergeHistory(
  previous: Sample[],
  incoming: Sample[],
  retentionSec = 60,
  capacity = 12000,
): Sample[] {
  const result = previous.slice();
  let seq = result.at(-1)?.seq ?? -1;
  let elapsed = result.at(-1)?.elapsedMs ?? -1;
  for (const sample of incoming) {
    if (sample.seq <= seq || sample.elapsedMs < elapsed) continue;
    result.push(sample);
    seq = sample.seq;
    elapsed = sample.elapsedMs;
  }
  const cutoff = elapsed - retentionSec * 1000;
  let index = 0;
  while (index < result.length && result[index]!.elapsedMs < cutoff) index++;
  return result.slice(Math.max(index, result.length - capacity));
}
