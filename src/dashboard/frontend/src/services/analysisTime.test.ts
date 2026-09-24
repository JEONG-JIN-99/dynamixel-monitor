import { expect, it } from "vitest";
import {
  elapsedTime,
  clockTime,
  timeOrigin,
  durationText,
} from "./analysisTime";
it("formats subsecond, minute, hour and multi-day elapsed values", () => {
  expect(elapsedTime(75)).toBe("1:15");
  expect(elapsedTime(735)).toBe("12:15");
  expect(elapsedTime(4355)).toBe("01:12:35");
  expect(elapsedTime(86400 + 8130)).toBe("1일 02:15:30");
  expect(elapsedTime(0.125, true)).toBe("0:00.125");
  expect(durationText(100)).toBe("0.1초");
});
it("uses the existing acquisition timestamp and fixed Korean timezone", () => {
  const base = Date.parse("2026-09-24T14:59:59.900Z");
  expect(clockTime(base, true, true)).toBe("2026-09-24 23:59:59.9");
  expect(clockTime(base + 200, true, true)).toBe("2026-09-25 00:00:00.1");
  expect(
    timeOrigin([
      { elapsedMs: 1000, timestamp: null },
      { elapsedMs: 2000, timestamp: base + 2000 },
    ]),
  ).toBe(base);
  expect(timeOrigin([{ elapsedMs: 0 }])).toBeNull();
  expect(clockTime(null)).toBe("시각 미수신");
});
