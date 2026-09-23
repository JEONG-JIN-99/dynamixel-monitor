import type { MotorMetadata, RegisterReading, Sample } from "../types/motor";
export type Area = "EEPROM" | "RAM";
export interface RegisterDefinition {
  address: number;
  size: number;
  name: string;
  english: string;
  access: "R" | "RW";
  area: Area;
  scale?: number;
  unit?: string;
  signed?: boolean;
  firmware?: number;
}
type Definition = [
  number,
  number,
  string,
  string,
  "R" | "RW",
  number?,
  string?,
  boolean?,
  number?,
];
// ROBOTIS XM430-W210 / W350 Control Table; indirect mappings intentionally excluded.
const definitions: Definition[] = [
  [0, 2, "모델 번호", "Model Number", "R"],
  [2, 4, "모델 정보", "Model Information", "R"],
  [6, 1, "펌웨어 버전", "Firmware Version", "R"],
  [7, 1, "모터 ID", "ID", "RW"],
  [8, 1, "통신 속도", "Baud Rate", "RW"],
  [9, 1, "응답 지연 시간", "Return Delay Time", "RW", 2, "μs"],
  [10, 1, "드라이브 모드", "Drive Mode", "RW"],
  [11, 1, "동작 모드", "Operating Mode", "RW"],
  [12, 1, "보조 ID", "Secondary ID", "RW"],
  [13, 1, "프로토콜 유형", "Protocol Type", "RW"],
  [20, 4, "원점 오프셋", "Homing Offset", "RW", 1, "pulse", true],
  [24, 4, "이동 판정 임계값", "Moving Threshold", "RW", 0.229, "rpm"],
  [31, 1, "온도 제한", "Temperature Limit", "RW", 1, "°C"],
  [32, 2, "최대 전압 제한", "Max Voltage Limit", "RW", 0.1, "V"],
  [34, 2, "최소 전압 제한", "Min Voltage Limit", "RW", 0.1, "V"],
  [36, 2, "PWM 제한", "PWM Limit", "RW", 0.113, "%"],
  [38, 2, "전류 제한", "Current Limit", "RW", 2.69, "mA"],
  [44, 4, "속도 제한", "Velocity Limit", "RW", 0.229, "rpm"],
  [48, 4, "최대 위치 제한", "Max Position Limit", "RW", 1, "pulse"],
  [52, 4, "최소 위치 제한", "Min Position Limit", "RW", 1, "pulse"],
  [
    60,
    1,
    "시작 설정",
    "Startup Configuration",
    "RW",
    undefined,
    undefined,
    false,
    45,
  ],
  [63, 1, "자동 차단 설정", "Shutdown", "RW"],
  [64, 1, "토크 활성화", "Torque Enable", "RW"],
  [65, 1, "LED 상태", "LED", "RW"],
  [68, 1, "응답 수준", "Status Return Level", "RW"],
  [69, 1, "등록 명령 대기", "Registered Instruction", "R"],
  [70, 1, "하드웨어 오류 상태", "Hardware Error Status", "R"],
  [76, 2, "속도 I 게인", "Velocity I Gain", "RW"],
  [78, 2, "속도 P 게인", "Velocity P Gain", "RW"],
  [80, 2, "위치 D 게인", "Position D Gain", "RW"],
  [82, 2, "위치 I 게인", "Position I Gain", "RW"],
  [84, 2, "위치 P 게인", "Position P Gain", "RW"],
  [88, 2, "2차 피드포워드 게인", "Feedforward 2nd Gain", "RW"],
  [90, 2, "1차 피드포워드 게인", "Feedforward 1st Gain", "RW"],
  [98, 1, "통신 감시 타이머", "Bus Watchdog", "RW", 20, "ms", true],
  [100, 2, "목표 PWM", "Goal PWM", "RW", 0.113, "%", true],
  [102, 2, "목표 전류", "Goal Current", "RW", 2.69, "mA", true],
  [104, 4, "목표 속도", "Goal Velocity", "RW", 0.229, "rpm", true],
  [108, 4, "프로파일 가속도", "Profile Acceleration", "RW"],
  [112, 4, "프로파일 속도", "Profile Velocity", "RW"],
  [116, 4, "목표 위치", "Goal Position", "RW", 1, "pulse", true],
  [120, 2, "실시간 틱", "Realtime Tick", "R", 1, "ms"],
  [122, 1, "이동 여부", "Moving", "R"],
  [123, 1, "이동 상태", "Moving Status", "R"],
  [124, 2, "현재 PWM", "Present PWM", "R", 0.113, "%", true],
  [126, 2, "현재 전류", "Present Current", "R", 2.69, "mA", true],
  [128, 4, "현재 속도", "Present Velocity", "R", 0.229, "rpm", true],
  [132, 4, "현재 위치", "Present Position", "R", 1, "pulse", true],
  [136, 4, "속도 궤적", "Velocity Trajectory", "R", 0.229, "rpm", true],
  [140, 4, "위치 궤적", "Position Trajectory", "R", 1, "pulse", true],
  [144, 2, "입력 전압", "Present Input Voltage", "R", 0.1, "V"],
  [146, 1, "모터 온도", "Present Temperature", "R", 1, "°C"],
  [
    147,
    1,
    "백업 준비 상태",
    "Backup Ready",
    "R",
    undefined,
    undefined,
    false,
    45,
  ],
];
export const controlTable: RegisterDefinition[] = definitions.map(
  ([address, size, name, english, access, scale, unit, signed, firmware]) => ({
    address,
    size,
    name,
    english,
    access,
    scale,
    unit,
    signed,
    firmware,
    area: address < 64 ? "EEPROM" : "RAM",
  }),
);
export const supportedModels = ["XM430-W210", "XM430-W350"];
export function manualUrl(model: string) {
  return `https://emanual.robotis.com/docs/en/dxl/x/${model === "XM430-W350" ? "xm430-w350" : "xm430-w210"}/#control-table`;
}
const numeric = (value: unknown): value is number =>
  typeof value === "number" && Number.isFinite(value);
const format = (value: number) =>
  value.toLocaleString("ko-KR", { maximumFractionDigits: 5 });
function decode(def: RegisterDefinition, raw: number) {
  return def.signed && raw >= 2 ** (def.size * 8 - 1)
    ? raw - 2 ** (def.size * 8)
    : raw;
}
function convert(
  def: RegisterDefinition,
  raw: number,
  driveMode: number | null,
) {
  const n = decode(def, raw);
  const plain = {
    value: format(n),
    unit: def.unit ?? "—",
    detail: "원시값 그대로 표시",
  };
  if (def.address === 8) {
    const baud = [
      9600, 57600, 115200, 1000000, 2000000, 3000000, 4000000, 4500000,
    ][n];
    return {
      value: baud ? format(baud) : `미정의 (${n})`,
      unit: "bps",
      detail: "공식 통신 속도 코드표 적용",
    };
  }
  if (def.address === 11)
    return {
      value:
        (
          {
            0: "전류 제어",
            1: "속도 제어",
            3: "위치 제어",
            4: "확장 위치 제어",
            5: "전류 기반 위치 제어",
            16: "PWM 제어",
          } as Record<number, string>
        )[n] ?? `미정의 (${n})`,
      unit: "—",
      detail: "동작 모드 코드 해석",
    };
  if ([64, 65, 69, 122, 147].includes(def.address)) {
    const labels: Record<number, string[]> = {
      64: ["비활성", "활성"],
      65: ["꺼짐", "켜짐"],
      69: ["없음", "대기 중"],
      122: ["멈춤", "이동 중"],
      147: ["백업 없음", "백업 있음"],
    };
    return {
      value: labels[def.address]![n] ?? `미정의 (${n})`,
      unit: "—",
      detail: "상태 코드 해석",
    };
  }
  if ([10, 60, 63, 70, 123].includes(def.address))
    return {
      value: `0x${n.toString(16).toUpperCase().padStart(2, "0")}`,
      unit: "비트",
      detail: `비트값: ${n.toString(2).padStart(8, "0")}`,
    };
  if (def.address === 98 && n <= 0)
    return {
      value: n === -1 ? "통신 감시 오류" : "사용 안 함",
      unit: "—",
      detail: "특수 상태 코드 해석",
    };
  if ([108, 112].includes(def.address)) {
    if (driveMode == null)
      return {
        value: "모드 확인 필요",
        unit: "—",
        detail:
          "드라이브 모드(10)의 시간 기반 프로파일 비트 확인 후 변환합니다.",
      };
    if (driveMode & 4)
      return {
        value: format(n),
        unit: "ms",
        detail: "시간 기반 프로파일 · 1 ms/단위",
      };
    const scale = def.address === 108 ? 214.577 : 0.229;
    return {
      value: format(n * scale),
      unit: def.address === 108 ? "rev/min²" : "rpm",
      detail:
        n === 0
          ? "속도 기반 프로파일 · 0은 무제한 설정"
          : `속도 기반 프로파일 · ${n} × ${scale}`,
    };
  }
  if (def.scale != null)
    return {
      value: format(n * def.scale),
      unit: def.unit!,
      detail: `${n} × ${def.scale} ${def.unit} = ${format(n * def.scale)} ${def.unit}`,
    };
  return plain;
}
export interface RegisterRow extends RegisterDefinition {
  rawText: string;
  value: string;
  displayUnit: string;
  status: string;
  source: string;
  detail: string;
  receivedAt: number | null;
}
export function registerRows(
  sample: Sample | null,
  metadata: MotorMetadata | undefined,
): RegisterRow[] {
  const readingFor = (address: number): RegisterReading | undefined => {
    const a = sample?.registers?.[address],
      b = metadata?.registers?.[address];
    return a && b ? (a.receivedAt >= b.receivedAt ? a : b) : (a ?? b);
  };
  const driveReading = readingFor(10);
  const driveMode =
    driveReading?.status === "received" && numeric(driveReading.raw)
      ? driveReading.raw
      : null;
  return controlTable.map((def) => {
    const base: RegisterRow = {
      ...def,
      rawText: "—",
      value: "—",
      displayUnit: def.unit ?? "—",
      status: "미수신",
      source: "—",
      detail: "해당 주소의 값이 아직 제공되지 않았습니다.",
      receivedAt: null,
    };
    const reading = readingFor(def.address);
    if (reading) {
      if (reading.status !== "received")
        return {
          ...base,
          status: reading.status === "unsupported" ? "미지원" : "읽기 오류",
          detail: reading.error ?? "주소 읽기 결과를 확인하세요.",
          receivedAt: reading.receivedAt,
        };
      if (
        !numeric(reading.raw) ||
        !Number.isInteger(reading.raw) ||
        reading.raw < (def.signed ? -(2 ** (def.size * 8 - 1)) : 0) ||
        reading.raw >= 2 ** (def.size * 8)
      )
        return {
          ...base,
          status: "읽기 오류",
          detail: "주소 크기에 맞는 정수 원시값이 아닙니다.",
        };
      const converted = convert(def, reading.raw, driveMode);
      return {
        ...base,
        rawText: format(reading.raw),
        value: converted.value,
        displayUnit: converted.unit,
        status: "수신",
        source: "주소 읽기",
        detail: converted.detail,
        receivedAt: reading.receivedAt,
      };
    }
    if (
      def.firmware &&
      metadata?.firmware != null &&
      metadata.firmware < def.firmware
    )
      return {
        ...base,
        status: "미지원",
        detail: `펌웨어 V${def.firmware} 이상에서 지원합니다.`,
      };
    const metaValue =
      def.address === 0
        ? metadata?.modelNumber
        : def.address === 6
          ? metadata?.firmware
          : null;
    if (numeric(metaValue))
      return {
        ...base,
        rawText: format(metaValue),
        value: format(metaValue),
        status: "메타데이터",
        source: "모터 메타데이터",
        detail: "수집 시작 시 저장된 모터 정보입니다.",
      };
    if (!sample) return base;
    // Existing CSV transport already converted these values; never fabricate raw readings by division.
    const fields: Record<number, [keyof Sample, number, string, boolean]> = {
      7: ["id", 1, "—", true],
      70: ["hwError", 1, "비트", true],
      116: ["goalPosition", 1, "pulse", true],
      120: ["realtimeTick", 1, "ms", true],
      122: ["moving", 1, "—", true],
      123: ["movingStatus", 1, "비트", true],
      124: ["pwm", 1, "%", false],
      126: ["current", 1000, "mA", false],
      128: ["velocity", 1, "rpm", false],
      132: ["position", 1, "pulse", true],
      136: ["velocityTrajectory", 1, "rpm", false],
      140: ["positionTrajectory", 1, "pulse", true],
      144: ["voltage", 1, "V", false],
      146: ["temperature", 1, "°C", true],
    };
    const field = fields[def.address];
    if (!field) return base;
    const [key, scale, unit, hasRaw] = field;
    const v = sample[key];
    const value = typeof v === "boolean" ? Number(v) : v;
    if (!numeric(value)) return base;
    const command = def.address === 116 && sample.goalSource === "command";
    const converted = hasRaw
      ? convert(def, value, driveMode)
      : {
          value: format(value * scale),
          unit,
          detail:
            "수신한 변환값입니다. 원시값은 현재 전송 데이터에 포함되지 않습니다.",
        };
    return {
      ...base,
      rawText: hasRaw ? format(value) : "—",
      value: converted.value,
      displayUnit: converted.unit,
      status: command ? "명령 기록" : hasRaw ? "수신" : "변환값 수신",
      source: command ? "실험 명령 기록" : "측정 샘플",
      detail: command
        ? "실험 프로그램이 기록한 목표 명령입니다. 해당 주소를 직접 읽은 값과 구분합니다."
        : converted.detail,
      receivedAt: sample.timestamp ?? sample.receivedAt,
    };
  });
}
