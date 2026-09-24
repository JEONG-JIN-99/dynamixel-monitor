import { expect, it } from "vitest";
import { faultEpisodes } from "./faultEpisodes";
import { analysisPoint } from "./analysis";
function point(t: number, codes: string[] | null = []) {
  return analysisPoint({
    id: 1,
    model: "XM430-W210",
    elapsedMs: t,
    timestamp: 100000 + t,
    registers: {},
    diagnosis:
      codes == null
        ? null
        : { state: codes.length ? "fault" : "normal", codes },
  });
}
it("groups each code independently, separates recurrences, newest first", () => {
  const rows = faultEpisodes(
    [
      point(0),
      point(100, ["friction"]),
      point(200, ["friction", "overload"]),
      point(300, ["overload"]),
      point(400),
      point(500, ["friction"]),
    ],
    100,
    true,
  );
  expect(rows.map((r) => [r.code, r.startMs, r.endMs, r.ending])).toEqual([
    ["friction", 500, null, "ongoing"],
    ["overload", 200, 400, "resolved"],
    ["friction", 100, 300, "resolved"],
  ]);
  expect(rows[1]?.startTimestamp).toBe(100200);
});
it("does not invent starts before the selected window or after missing data", () => {
  const rows = faultEpisodes(
    [
      point(60000, ["friction"]),
      point(60100, ["friction"]),
      point(61000, ["friction"]),
      point(61100),
    ],
    100,
    true,
  );
  expect(
    rows.map((r) => [r.leftBoundary, r.ending, r.endMs, r.lastMs]),
  ).toEqual([
    ["gap", "resolved", 61100, 61000],
    ["window", "unconfirmed", null, 60100],
  ]);
});
it("unknown diagnosis cannot resolve an incident; terminated recordings cannot claim ongoing", () => {
  const rows = faultEpisodes(
    [
      point(0, ["overload"]),
      point(100, null),
      point(200),
      point(300, ["friction"]),
    ],
    100,
    false,
  );
  expect(rows[0]?.ending).toBe("unconfirmed");
  expect(rows[1]?.endMs).toBeNull();
  expect(rows[1]?.lastMs).toBe(0);
  expect(faultEpisodes([point(0), point(100)], 100, false)).toEqual([]);
});
