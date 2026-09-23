import { describe, expect, it } from "vitest";
import { diagnosisView } from "./overview";
import type { Sample } from "../types/motor";
const sample = (data: Partial<Sample>) => data as Sample;
describe("algorithm diagnosis boundary", () => {
  it("does not infer normal from hardware or experiment labels", () => {
    expect(
      diagnosisView(
        sample({ status: "normal", hwError: 0, condition: "normal" }),
      ).state,
    ).toBe("waiting");
    expect(diagnosisView(null).state).toBe("waiting");
  });
  it("localizes multiple faults and keeps unknown faults abnormal", () => {
    expect(
      diagnosisView(
        sample({
          diagnosis: { state: "fault", codes: ["overload", "gear_backlash"] },
        }),
      ).label,
    ).toBe("과부하 · 기어 백래시");
    expect(
      diagnosisView(
        sample({ diagnosis: { state: "fault", codes: ["future_fault"] } }),
      ),
    ).toMatchObject({ state: "fault", label: "미분류 이상" });
  });
  it("requires an explicit consistent normal result", () => {
    expect(
      diagnosisView(sample({ diagnosis: { state: "normal", codes: [] } }))
        .state,
    ).toBe("normal");
    expect(
      diagnosisView(
        sample({ diagnosis: { state: "normal", codes: ["friction"] } }),
      ).state,
    ).toBe("waiting");
  });
});
