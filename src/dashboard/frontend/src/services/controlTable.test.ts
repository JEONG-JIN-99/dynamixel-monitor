import { describe, expect, it } from "vitest";
import { controlTable, registerRows } from "./controlTable";
import type { Sample, MotorMetadata, RegisterReading } from "../types/motor";
const reading = (
  raw: number,
  status: RegisterReading["status"] = "received",
  receivedAt = 1000,
): RegisterReading => ({ raw, status, receivedAt });
const sample = (properties: Partial<Sample>) => properties as Sample;
const metadata = (properties: Partial<MotorMetadata>) =>
  properties as MotorMetadata;
const at = (rows: ReturnType<typeof registerRows>, address: number) =>
  rows.find((row) => row.address === address)!;
describe("official XM430 register table", () => {
  it("covers all 53 distinct general registers and no indirect addresses", () => {
    expect(controlTable).toHaveLength(53);
    expect(new Set(controlTable.map((r) => r.address)).size).toBe(53);
    expect(controlTable.filter((r) => r.area === "EEPROM")).toHaveLength(22);
    expect(controlTable.filter((r) => r.area === "RAM")).toHaveLength(31);
    expect(controlTable.at(-1)?.address).toBe(147);
  });
  it("never substitutes documentation defaults or experiment settings for readings", () => {
    const rows = registerRows(
      null,
      metadata({ settings: { baudrate: 57600, current_limit: 1193 } }),
    );
    expect(rows.every((r) => r.rawText === "—" && r.value === "—")).toBe(true);
  });
  it("preserves unsigned raw bytes and decodes signed physical quantities", () => {
    const rows = registerRows(
      sample({
        registers: {
          126: reading(65535),
          128: reading(4294967295),
          98: reading(255),
        },
      }),
      undefined,
    );
    expect(at(rows, 126)).toMatchObject({
      rawText: "65,535",
      value: "-2.69",
      displayUnit: "mA",
    });
    expect(at(rows, 128).value).toBe("-0.229");
    expect(at(rows, 98).value).toBe("통신 감시 오류");
  });
  it("uses supplied converted CSV values without reverse engineering raw values", () => {
    const rows = registerRows(
      sample({
        current: 0.43309,
        velocity: 14.656,
        goalPosition: 3172,
        goalSource: "command",
        receivedAt: 1000,
      }),
      undefined,
    );
    expect(at(rows, 126)).toMatchObject({
      rawText: "—",
      value: "433.09",
      status: "변환값 수신",
    });
    expect(at(rows, 128)).toMatchObject({ rawText: "—", value: "14.656" });
    expect(at(rows, 116).status).toBe("명령 기록");
  });
  it("converts profiles only with a received Drive Mode", () => {
    expect(
      at(
        registerRows(sample({ registers: { 108: reading(10) } }), undefined),
        108,
      ).value,
    ).toBe("모드 확인 필요");
    expect(
      at(
        registerRows(
          sample({ registers: { 10: reading(4), 108: reading(10) } }),
          undefined,
        ),
        108,
      ),
    ).toMatchObject({ value: "10", displayUnit: "ms" });
    expect(
      at(
        registerRows(
          sample({ registers: { 10: reading(0), 108: reading(10) } }),
          undefined,
        ),
        108,
      ),
    ).toMatchObject({ value: "2,145.77", displayUnit: "rev/min²" });
  });
  it("distinguishes unsupported firmware, read failure, and a received zero", () => {
    const rows = registerRows(
      sample({
        registers: {
          70: reading(0),
          84: reading(0, "error"),
          65: reading(256),
        },
      }),
      metadata({ firmware: 44 }),
    );
    expect(at(rows, 70)).toMatchObject({
      rawText: "0",
      value: "0x00",
      status: "수신",
    });
    expect(at(rows, 60).status).toBe("미지원");
    expect(at(rows, 147).status).toBe("미지원");
    expect(at(rows, 84).status).toBe("읽기 오류");
    expect(at(rows, 65).status).toBe("읽기 오류");
  });
  it("keeps a newer read error instead of displaying an older successful value", () => {
    const rows = registerRows(
      sample({ registers: { 126: reading(10, "received", 100) } }),
      metadata({ registers: { 126: reading(0, "error", 200) } }),
    );
    expect(at(rows, 126)).toMatchObject({ value: "—", status: "읽기 오류" });
  });
});
