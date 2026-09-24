# 협업자 요청사항 — 수집·알고리즘·백엔드 통합 계약

기준: 이 폴더에 포함된 프론트엔드와 참조 백엔드, telemetry schemaVersion **1**.
이 문서는 현재 코드가 요구하는 인터페이스를 설명합니다. 화면 개발 설명을 사용자 UI에 추가할 필요는 없습니다.

## 1. 역할과 권장 통합 순서

프론트엔드는 원시 레지스터를 표시 단위로 변환하고 그래프·표·알림·기록을 그립니다. 수집이나 고장 판정 알고리즘은 수행하지 않습니다. 추종 오차, 비트 해석, 상태 구간 묶기 같은 표시용 계산은 프론트에서 처리합니다.

협업자 구현 범위:

1. 모터 통신·제어 프로세스가 측정값과 설정값을 읽는다.
2. 알고리즘이 같은 측정 시점에 대응하는 판정 결과를 만든다.
3. 백엔드가 아래 JSON 형식으로 전송하고, 동일 데이터를 실험별 영구 저장한다.
4. 이력·제어·로그 API를 구현하거나 현재 참조 백엔드의 해당 부분을 유지한다.

두 가지 연결 방법이 있습니다.

- **현재 서버 유지:** `mock_source.py`/`control.py`의 가상 데이터 생산부에 대응하는 실제 수집 어댑터를 만들고 `TelemetryHub`로 snapshot·증분을 발행합니다. 수집은 SDK 전용 스레드/프로세스가 맡고 웹 이벤트 루프를 막지 않습니다.
- **협업자 서버로 교체:** 아래 HTTP/WS API를 같은 경로로 제공하고 빌드된 `frontend/dist`를 제공하거나 리버스 프록시로 같은 origin에 연결합니다. 저장 방식은 CSV·DB 어느 쪽이어도 됩니다.

현재 실제 실험 복사본은 일부 측정 주소의 CSV를 제공하는 호환 경로입니다. 53개 전부를 수집하거나 알고리즘 판정을 자동 생성하는 구현으로 간주하면 안 됩니다. SDK 오류, condition 이름 또는 하드웨어 오류 비트를 알고리즘 판정 대신 보내지 마세요.

## 2. 실행 대상과 연결 경로

| 항목 | 값 / 경로 |
|---|---|
| 제어 API 실행 대상 | `source: "mock"` 또는 `"real"` |
| 화면 수신 소스 | `mock` 또는 `csv` |
| 가상 실시간 연결 | `/ws/telemetry?source=mock` |
| 실제 실시간 연결 | `/ws/telemetry` 또는 `?source=csv` |
| 가상 화면 URL | `/?source=mock` (현재 기본값) |
| 실제 화면 URL | `/?source=csv` |

`csv`는 현재 수신 채널의 이름입니다. 협업자 서버가 직접 측정 JSON을 전송해도 이 이름을 유지하면 프론트 수정 없이 연결할 수 있습니다. `real`을 WebSocket source로 보내면 안 됩니다. 조회 소스 선택 자체가 실험 시작 명령은 아닙니다.

프론트는 동일 host의 `/api`와 `/ws`를 사용합니다. 개발에서는 `frontend/vite.config.ts`가 8000번 서버로 프록시합니다. 다른 주소에 백엔드를 두려면 프록시 또는 수신 서비스 설정을 조정해야 합니다. 현재 제어 POST는 Origin과 Host가 다르면 거부하므로 Vite/리버스 프록시의 Origin 전달 정책도 확인합니다. 임의로 검증을 제거하지 말고 허용할 개발 origin을 명시적으로 정합니다.

## 3. 시간·식별자·순서 규칙

| 필드 | 타입 | 규칙 |
|---|---|---|
| `schemaVersion` | 정수 | 메시지·HTTP 이력 응답 최상위에서 `1` |
| `serverSessionId` | 문자열 | 서버 시작마다 새 ID. 동일 서버 실행 중 유지 |
| `sourceSessionId` | 문자열/null | 데이터 스트림 세션. 실험 전 null 가능; 실행·파일 교체 시 변경 |
| `runId` | 문자열/null | 실험 실행마다 고유 ID. 샘플에서는 null 불가 |
| `busId` | 문자열 | 장치 버스 식별자 |
| `seq` | 정수 | 한 스트림 전체에서 엄격 증가, 여러 모터도 중복 없이 부여 |
| `id` / `model` | 정수 / 문자열 | ID 0~252, `XM430-W210` 또는 `XM430-W350` |
| `elapsedMs` | 숫자 | 실험 시작부터 경과한 밀리초, 순서대로 비감소 |
| `timestamp` | 숫자 | 실제 측정 시각의 Unix 밀리초. 초 단위를 보내지 않음 |
| `receivedAt` | 숫자 | 수집 프로그램이 취득한 시각, Unix 밀리초 |
| `basePosition` | 숫자/null, 선택 | 실험 시작 시 위치 원시 pulse. 3D 축 회전 원점으로 사용 |

샘플 안의 세션·실험 ID는 snapshot/현재 experiment와 일치해야 합니다. 동일 실험 재접속 때 seq를 1부터 다시 보내지 마세요. 초기 snapshot의 중복 구간은 프론트가 seq로 제거합니다. 다른 세션의 증분은 버립니다.

`Realtime Tick(120)`은 모터 내부 순환 타이머이므로 Unix timestamp나 실험 경과시간 대용으로 사용할 수 없습니다. 시계 보정이 있어도 elapsedMs는 단조 시계 기준으로 유지합니다.

**현재 UI 제한:** 모터 선택 키는 `model + id`입니다. 서로 다른 버스의 동일 모델·동일 ID는 화면에서 충돌합니다. 현 프로토타입은 단일 실행·주로 단일 모터를 기준으로 합니다. 다중 버스 확장 시 프론트 키/메타데이터/이력 조회를 함께 확장해야 합니다.

## 4. 권장 샘플: 원시 레지스터 형식

타입 원본: `frontend/src/types/motor.ts`의 `RegisterSample`, `RegisterReading`.
아래는 일부 주소만 보인 설명 예시입니다. 53개 주소가 모두 들어 있는 실행 가능한 JSON 예시는 [contracts/examples.json](contracts/examples.json)의 `snapshot.latest`에 있습니다.

```json
{
  "serverSessionId": "server-1",
  "sourceSessionId": "run-1:1",
  "runId": "run-1",
  "busId": "USB-1",
  "seq": 125,
  "id": 1,
  "model": "XM430-W210",
  "elapsedMs": 12400,
  "timestamp": 1790000012400,
  "receivedAt": 1790000012402,
  "basePosition": 100,
  "registers": {
    "11": {"raw": 4, "receivedAt": 1790000000000, "status": "received"},
    "126": {"raw": 100, "receivedAt": 1790000012400, "status": "received"},
    "128": {"raw": -20, "receivedAt": 1790000012400, "status": "received"},
    "132": {"raw": 2100, "receivedAt": 1790000012400, "status": "received"},
    "140": {"raw": 2110, "receivedAt": 1790000012400, "status": "received"}
  },
  "diagnosis": {"state": "normal", "codes": []}
}
```

`registers`는 **주소를 십진 문자열 키**로 쓰는 객체입니다. 각 항목:

| 필드 | 타입 / 의미 |
|---|---|
| `raw` | 원시 정수 또는 null. 이미 A/rpm으로 변환한 실수를 넣지 않음 |
| `receivedAt` | 그 레지스터를 실제 취득한 시각, Unix ms |
| `status` | `received` / `unsupported` / `error` |
| `error` | 선택 문자열, 읽기 실패 사유 |

지원하지 않는 항목: `{"raw":null,"receivedAt":1790000012400,"status":"unsupported"}`.
읽기 실패: `{"raw":null,"receivedAt":1790000012400,"status":"error","error":"timeout"}`.
실패 값을 0으로 대체하거나 이전 값을 새 시각으로 찍지 마세요. null은 미측정이며 정상 판정이 아닙니다. JSON에는 NaN·Infinity를 보내지 않습니다.

Signed 레지스터는 부호 있는 정수로 보내는 방식을 권장합니다. 현재 프론트는 레지스터 크기의 2의 보수 unsigned 정수도 해석합니다. 비트필드는 해석한 문자열이 아닌 정수를 보냅니다.

### 단위와 동시성

| 주소 | 프론트의 표시 변환 |
|---|---|
| 126 현재 전류 | raw × 0.00269 → A (테이블에서는 ×2.69 mA) |
| 124 현재 PWM | raw × 0.113 → % |
| 128 / 136 속도·속도 궤적 | raw × 0.229 → rpm |
| 132 / 140 / 116 위치·궤적·목표 | 원시 pulse 유지 |
| 144 입력 전압 | raw × 0.1 → V |
| 146 온도 | raw → °C |

한 수집 프레임에서 취득한 위치·위치 궤적(132/140), 속도·속도 궤적(128/136)은 동일한 취득 시각을 부여합니다. 서로 다른 시점의 값을 동시 측정처럼 꾸미면 안 됩니다. 프론트는 쌍의 receivedAt이 같고 동작 모드가 유효할 때만 추종 오차를 계산합니다.

EEPROM·설정값은 저속 갱신하고 `metadata[].registers`로 전달할 수 있습니다. 모든 주소를 10 Hz로 매번 물리적으로 읽을 필요는 없습니다. 다만 모터 표에 53개를 표시하려면 각각의 값 또는 unsupported/error 상태가 필요합니다. 설정 캐시를 샘플에 함께 넣을 때 원래 receivedAt을 유지합니다. 이력에는 그 시점에 적용된 설정값 또는 설정 변경 기록을 복원할 수 있어야 하며, 최신 설정을 과거 전체에 소급 적용하면 안 됩니다. 연속 그래프용 현재 측정값은 각 샘플에 포함합니다.

`basePosition`은 선택이지만 새로고침·60초 창 이동 이후에도 동일한 회전 원점을 원하면 매 샘플과 이력에 보존하는 것을 권장합니다. 생략하면 프론트가 처음 받은 유효 위치를 임시 기준으로 삼습니다.

### 53개 항목 목록

아래는 현재 프론트의 `controlTable.ts` 정의입니다. 간접 주소·간접 데이터는 전송 대상에서 제외했습니다. 모터/펌웨어에 따라 지원 여부를 확인하고 미지원으로 표시합니다. RW 항목을 읽기 위해 임의로 쓰거나 토크를 해제할 필요는 없습니다.

| 주소 | 크기(byte) | 항목 | 접근 |
|---|---|---|---|
| 0 | 2 | 모델 번호 / Model Number | R |
| 2 | 4 | 모델 정보 / Model Information | R |
| 6 | 1 | 펌웨어 버전 / Firmware Version | R |
| 7 | 1 | 모터 ID / ID | RW |
| 8 | 1 | 통신 속도 / Baud Rate | RW |
| 9 | 1 | 응답 지연 시간 / Return Delay Time | RW |
| 10 | 1 | 드라이브 모드 / Drive Mode | RW |
| 11 | 1 | 동작 모드 / Operating Mode | RW |
| 12 | 1 | 보조 ID / Secondary ID | RW |
| 13 | 1 | 프로토콜 유형 / Protocol Type | RW |
| 20 | 4 | 원점 오프셋 / Homing Offset | RW |
| 24 | 4 | 이동 판정 임계값 / Moving Threshold | RW |
| 31 | 1 | 온도 제한 / Temperature Limit | RW |
| 32 | 2 | 최대 전압 제한 / Max Voltage Limit | RW |
| 34 | 2 | 최소 전압 제한 / Min Voltage Limit | RW |
| 36 | 2 | PWM 제한 / PWM Limit | RW |
| 38 | 2 | 전류 제한 / Current Limit | RW |
| 44 | 4 | 속도 제한 / Velocity Limit | RW |
| 48 | 4 | 최대 위치 제한 / Max Position Limit | RW |
| 52 | 4 | 최소 위치 제한 / Min Position Limit | RW |
| 60 | 1 | 시작 설정 / Startup Configuration | RW |
| 63 | 1 | 자동 차단 설정 / Shutdown | RW |
| 64 | 1 | 토크 활성화 / Torque Enable | RW |
| 65 | 1 | LED 상태 / LED | RW |
| 68 | 1 | 응답 수준 / Status Return Level | RW |
| 69 | 1 | 등록 명령 대기 / Registered Instruction | R |
| 70 | 1 | 하드웨어 오류 상태 / Hardware Error Status | R |
| 76 | 2 | 속도 I 게인 / Velocity I Gain | RW |
| 78 | 2 | 속도 P 게인 / Velocity P Gain | RW |
| 80 | 2 | 위치 D 게인 / Position D Gain | RW |
| 82 | 2 | 위치 I 게인 / Position I Gain | RW |
| 84 | 2 | 위치 P 게인 / Position P Gain | RW |
| 88 | 2 | 2차 피드포워드 게인 / Feedforward 2nd Gain | RW |
| 90 | 2 | 1차 피드포워드 게인 / Feedforward 1st Gain | RW |
| 98 | 1 | 통신 감시 타이머 / Bus Watchdog | RW |
| 100 | 2 | 목표 PWM / Goal PWM | RW |
| 102 | 2 | 목표 전류 / Goal Current | RW |
| 104 | 4 | 목표 속도 / Goal Velocity | RW |
| 108 | 4 | 프로파일 가속도 / Profile Acceleration | RW |
| 112 | 4 | 프로파일 속도 / Profile Velocity | RW |
| 116 | 4 | 목표 위치 / Goal Position | RW |
| 120 | 2 | 실시간 틱 / Realtime Tick | R |
| 122 | 1 | 이동 여부 / Moving | R |
| 123 | 1 | 이동 상태 / Moving Status | R |
| 124 | 2 | 현재 PWM / Present PWM | R |
| 126 | 2 | 현재 전류 / Present Current | R |
| 128 | 4 | 현재 속도 / Present Velocity | R |
| 132 | 4 | 현재 위치 / Present Position | R |
| 136 | 4 | 속도 궤적 / Velocity Trajectory | R |
| 140 | 4 | 위치 궤적 / Position Trajectory | R |
| 144 | 2 | 입력 전압 / Present Input Voltage | R |
| 146 | 1 | 모터 온도 / Present Temperature | R |
| 147 | 1 | 백업 준비 상태 / Backup Ready | R |

모델별·펌웨어별 제어 동작과 제한은 실제 수집 구현자가 장치 사양에 맞춰 확인해야 합니다. UI의 설정한계선은 장치 설정값 표시이며 알고리즘의 고장 판정 임계선이 아닙니다.

## 5. 알고리즘 결과

```json
{"state":"waiting","codes":[]}
{"state":"normal","codes":[]}
{"state":"fault","codes":["friction","overload"]}
```

각 줄은 별개의 JSON 판정 예시입니다. `diagnosis`가 null이면 판정 미수신입니다.

- `codes`는 새로 발생한 코드만이 아니라 **그 샘플 시점의 모든 활성 이상 코드**입니다.
- normal은 빈 배열, fault는 하나 이상의 코드, waiting은 판정 준비 중입니다.
- 같은 이상이 지속되면 같은 코드를 계속 보냅니다. normal 또는 다른 활성 목록에서 코드가 빠지면 해제로 간주합니다.
- waiting/null/수신 단절만으로는 해제됐다고 판단하지 않습니다.
- 알고리즘 지연이 있다면 해당 샘플에 판정을 붙여 순서대로 발행하는 방식을 권장합니다. 이미 발행한 seq의 판정을 나중에 수정해서 재전송하는 프로토콜은 현재 지원하지 않습니다. 과거 재판정이 필요하면 별도 revision/reset 계약을 추가해야 합니다.
- 실험 조건 `condition_name`과 판정 `diagnosis`는 별개입니다. 정상 조건 실험이라도 알고리즘이 마찰을 검출할 수 있습니다.

| 코드 | 화면 명칭 |
|---|---|
| `friction` | 마찰 |
| `overload` | 과부하 |
| `overvoltage` | 과전압 |
| `undervoltage` | 과소전압 |
| `undercurrent` | 과소전류 |
| `gear_backlash` | 기어 백래시 |

새 코드를 추가하면 `frontend/src/services/overview.ts`의 명칭 매핑도 추가합니다. 미등록 코드는 미분류 이상으로 표시됩니다. 알고리즘 신뢰도·특징량은 현재 표시 계약에 없습니다.

알림은 프론트가 판정 전이로 생성합니다. 사용자 확인 여부·확인 시각은 localStorage에 별도 저장합니다. 첫 snapshot의 이미 종료된 과거 이상을 새 미확인 알림으로 소급 생성하지 않고, 실행 중 최신 시점의 활성 이상과 이후 새 발생을 알립니다. 전체 과거 이상은 상세 분석·로그의 상태 이력에서 볼 수 있습니다.

## 6. WebSocket 메시지

서버가 전송하며 프론트는 구독합니다. 모든 메시지는 JSON 객체이고 공통으로 `schemaVersion:1`, `serverSessionId`, `sourceSessionId`를 포함합니다. 프론트가 먼저 구독 명령을 보내기를 기다리지 마세요.

### 최초 `snapshot` / 재동기화 `reset`

| 필드 | 타입 / 내용 |
|---|---|
| `type` | `snapshot` 또는 `reset` |
| `runId` | 실행 ID, 실행 전 null |
| `experiment` | 아래 Experiment 또는 null |
| `metadata` | 아래 MotorMetadata 배열; 없으면 [] |
| `history` | 시퀀스 순으로 정렬한 최근 60초 Sample 배열 |
| `latest` | 최신 Sample 또는 null |
| `retentionSec` | 60 |
| `capacity` | 양의 정수; 최근 60초 전체 모터 데이터를 담을 수 있는 크기 |
| `seq` | snapshot의 최신 스트림 순번, 실행 전 0 |
| `events` | 이벤트 배열; 없으면 [] |
| `system` | 아래 SystemState |

재접속 시에도 먼저 snapshot을 보냅니다. 실행 변경/파일 교체/느린 클라이언트의 큐 초과는 reset으로 최신 상태를 다시 제공합니다. snapshot 획득과 증분 구독 사이에 샘플이 유실되지 않도록 서버에서 연결을 원자적으로 처리해야 합니다. 참고 구현은 `stream.py`입니다.

### 추가 측정 `samples`

```json
{
  "schemaVersion": 1,
  "type": "samples",
  "serverSessionId": "server-1",
  "sourceSessionId": "run-1:1",
  "samples": []
}
```

실제 전송에서는 samples에 4절의 전체 Sample 객체를 넣습니다. 0.1초마다 한 개 또는 여러 개를 묶어서 보내도 됩니다. 여러 개면 seq 순으로 보내며 평균이나 중간값으로 대체하지 않습니다. 현재 화면 반영 타이머는 약 100ms이고 프론트는 메시지에 포함된 모든 샘플을 처리합니다.

### 상태 변경 `system`

공통 필드 + `type:"system"`, `system:SystemState`, `experiment:Experiment|null`, `metadata:MotorMetadata[]`.
실험 상태가 바뀌면 즉시 발행하고, 데이터가 끊겨도 stale/error 상태를 전송해야 합니다. 실험 종료 후 가짜 측정 샘플을 계속 생성하면 안 됩니다.

### 선택 이벤트 `event`

공통 필드 + `type:"event"`, `event:{id,time,severity,message}`.
`time`은 시간대가 포함된 ISO 8601 문자열입니다. 연결/읽기 오류 등의 시스템 이벤트용이며 알고리즘 판정 알림을 대신하지 않습니다.

### Experiment

`runId:string`, `status:string`, `csvPath:string|null`, `metadataPath:string|null`, `motorModel:string`, `motorId:number`, `sampleIntervalSec:number`, `flushEveryRows:number`, `startedAt:ISO8601`, `endedAt:ISO8601|null`, `error:string|null`.

파일 경로는 브라우저에서 직접 열지 않습니다. 자체 서버가 CSV를 사용하지 않으면 csvPath/metadataPath는 null로 줄 수 있습니다. 상태는 `preparing → running → finishing → completed`, 오류/중단은 `failed`/`interrupted`를 사용합니다.

### SystemState

| 필드 | 타입 / 의미 |
|---|---|
| `sourceMode` | mock / csv |
| `validity` | waiting / valid / stale / error |
| `experimentStatus` | experiment.status와 동일 |
| `dataAgeSec` | 마지막 유효 측정 후 경과 초 또는 null |
| `configuredHz`, `observedHz` | 설정/관측 수집률 Hz 또는 null |
| `expectedFlushSec` | 저장 반영 주기 초 또는 null |
| `readerCaughtUp` | 이력 복원 완료 여부 boolean; 직접 스트림이면 준비 완료 시 true |
| `writerActive` | 수집·기록 실행 여부 boolean 또는 null |
| `error` | 오류 문자열 또는 null |

알림의 현재 발생 중 여부는 유효 연결·valid·running/finishing·readerCaughtUp을 함께 사용합니다. 시작 전 waiting, 실험 종료 후 completed, 끊긴 수신은 stale로 구분해야 합니다.

### MotorMetadata

`id`, `model`, `modelNumber:number|null`, `firmware:number|null`, `settings:object`, `source:string`, `simulated:boolean`, `registers?:Record<string,RegisterReading>`, `limits:{current,temperature,voltageMin,voltageMax}`.
limits 값은 숫자 또는 null이며 표시 단위는 A/°C/V입니다. 그래프 설정한계선과 모드 해석에는 registers의 11,31,32,34,36,38 등이 사용되므로 이 원시 설정값도 제공해야 합니다. 메타데이터만으로 현재 측정값을 대신하지 않습니다.

## 7. 상세 분석의 긴 구간 API

```http
GET /api/history?source=mock&runId=run-1&sourceSessionId=run-1:1&durationSec=300&motorId=1&model=XM430-W210
```

- `durationSec`: 60, 300, 600, 1800, 3600, **0=전체**.
- 기준은 요청 시점의 최신 측정 elapsedMs. 최근 N초의 **전체 원본**을 반환합니다.
- `afterSeq`는 선택, 기본0. 지정하면 그 순번보다 큰 데이터만 반환합니다. 현재 프론트의 구간 변경은 전체 구간을 요청합니다.
- motorId/model은 선택 필터입니다.
- 현재 UI의 60초 모드는 WS 버퍼를 사용하고, 그보다 긴 구간에서 HTTP를 요청합니다.

```json
{
  "schemaVersion": 1,
  "serverSessionId": "server-1",
  "sourceSessionId": "run-1:1",
  "runId": "run-1",
  "throughSeq": 3001,
  "latestElapsedMs": 300000,
  "samples": []
}
```

samples는 WS와 동일한 형식·ID·seq·timestamp·diagnosis를 가진 원본 배열입니다. `throughSeq`는 요청 시 확정한 저장/조회 상한입니다. 그 상한까지만 읽어 응답하고 미완성 CSV 행은 포함하지 마세요. WS로 발행한 값이 이후 같은 seq의 이력과 달라져서는 안 됩니다.

프론트는 HTTP 대기 중 WS를 임시 보관하고, HTTP 완료 후 겹치는 seq를 제거해서 이어 붙입니다. 유한 구간은 오래된 데이터를 버리고 전체 모드는 누적합니다. 접속이 끊겼다가 돌아오면 이력을 다시 요청합니다.

실험/세션이 요청과 달라졌으면 **409**, 아직 이력 없음 **404/503**, 파라미터 오류 **422**. 실패 시 다른 실험의 데이터나 가상 데이터를 대신 반환하지 마세요. 현재 API는 페이지네이션 없는 전체 구간 응답이므로 장시간·고주파 데이터의 응답 크기/브라우저 메모리 한계는 추가 설계 대상입니다.

## 8. 제어 API

프론트는 `/api/control`을 약 1초마다 조회합니다. 서버 시작으로 실험이 자동 시작되면 안 됩니다.

| 메서드·경로 | 요청 |
|---|---|
| GET `/api/control` | 없음 |
| POST `/api/control/config` | `{"source":"mock 또는 real","config":{...}}` |
| POST `/api/control/start` | `{"configId":"저장된 설정 ID"}` |
| POST `/api/control/stop` | `{"runId":"현재 실행 ID"}` |

모든 성공 응답은 같은 ControlState:

```json
{"saved":null,"defaults":{},"run":null,"active":false,"externalActive":false}
```

- `defaults`: 아래 Config 전체 기본값. 빈 객체는 설명용이며 실제 응답은 모든 설정값을 채웁니다.
- `saved`: null 또는 `{id,source,config,savedAt}`. source는 mock/real, savedAt은 ISO 8601.
- `run`: null 또는 9절 RunRecord.
- `active`: 준비·실행·왕복 종료 대기 동안 true.
- `externalActive`: 서버 밖의 별도 실험이 장치를 사용 중이면 true.

Config는 TOML 섹션이 아닌 다음 평탄한 JSON 키를 사용합니다. 완전한 값 예시는 contracts/examples.json의 saveConfigRequest에 있습니다.

| 키 | 타입 / 단위 |
|---|---|
| motor_name, port | 문자열, 예: XM430-W210 / COM6 |
| motor_id, baudrate | 정수 |
| protocol_version | 2.0 |
| condition_name | normal/friction/overload/overvoltage/undervoltage/undercurrent/gear_backlash |
| load_kg | 숫자 kg |
| turns | 양수 회전수 |
| direction | 1 또는 -1 |
| acceleration_ms, profile_duration_ms | 정수 ms; 가속≤편도시간/2 |
| top_dwell_sec, bottom_dwell_sec | 0 이상 초 |
| max_cycles | 정수, 0=종료 요청까지 반복 |
| sample_interval_sec, print_interval_sec | 양수 초 |
| flush_every_rows | 양의 정수 |
| move_timeout_sec | 편도시간보다 큰 초 |
| position_tolerance_pulse | 0 이상 정수 pulse |
| torque_off_on_normal_exit | **false** |

저장은 모터를 움직이지 않고 설정 ID를 발급합니다. 시작은 그 ID의 확정 설정으로 새 실행·새 저장 폴더를 만듭니다. 실행 중 설정 변경·중복 시작·잘못된 실행 stop은 서버에서도 검증합니다. 충돌409, 값 오류422, 응답 오류 본문은 `{"detail":"사용자에게 보여줄 설명"}`입니다.

stop은 즉시 토크 해제가 아니라 `finishing`으로 바꾸고 현재 왕복을 마친 뒤 종료합니다. 토크 유지가 정상 종료 요구사항입니다. 실제 비상 정지·연결 단절 처리는 별도 장치 제어 정책이며 웹 종료 버튼과 혼동하지 마세요.

## 9. 로그 API와 영구 기록

| 경로 | 응답 |
|---|---|
| GET `/api/runs?year=2026&month=9&day=24&source=mock&offset=0&limit=30` | `{runs:RunRecord[],total:number,dates:string[]}` |
| GET `/api/runs/{runId}` | RunRecord |
| GET `/api/runs/{runId}/history?durationSec=0` | 7절 HistoryReply |

year/month/day/source는 생략 가능. source는 mock/real. 날짜 문자열은 `YYYY-MM-DD`, 정렬은 최신 실행 우선, total은 필터된 전체 개수이며 dates는 날짜 선택에 사용됩니다. 현재 limit 범위1~200입니다.

프론트에 필요한 RunRecord 필드:

| 필드 | 타입 |
|---|---|
| runId, source, status | 문자열; source mock/real |
| startedAt, endedAt | ISO 8601; endedAt은 null 가능 |
| date | 한국 시간 기준 YYYY-MM-DD |
| motorModel, motorId | 문자열, 정수 |
| condition | 조건 코드 문자열 |
| elapsedMs, completedCycles, rowCount, sampleIntervalSec | 숫자 |
| error | 문자열/null |
| metadata | MotorMetadata[] |

참조 백엔드는 여기에 config, serverSessionId, sourceSessionId, lastSeq, stopReason 등을 추가 저장합니다. 로그 분석은 completed/failed/interrupted 실행만 열며, 과거 실행의 마지막 판정을 현재 상태처럼 표시하지 않습니다.

**저장 요구:** 실행 ID, 확정 설정, 시작·종료 시각, 종료 사유, 모든 원본 레지스터와 원래 취득 시각, 판정 코드, seq를 보존합니다. CSV 형식 자체는 서버 구현 자유지만 WS와 HTTP 이력의 샘플 스키마는 같아야 합니다. 참조 가상 CSV는 registers와 diagnosis를 JSON 문자열 열로 기록하고, 원시 샘플의 basePosition도 보존합니다. metadata.json의 schemaVersion 2는 저장 포맷 버전이며 전송 schemaVersion 1과 별개입니다.

참고용 읽기 API도 있습니다: `/api/health`, `/api/experiment`, `/api/motors`. 전체 화면 통합의 중심은 WS·control·history·runs입니다. API 전체 목록은 실행 후 `/docs`에서 확인할 수 있으나, 동적 JSON 본문과 WS 상세는 이 문서·타입·예시를 기준으로 구현합니다.

## 10. 연결 검증 체크리스트

- [ ] 가상 모터로 설정 저장 → 시작 → 왕복 종료 → 로그 기록 분석이 된다.
- [ ] 최초 snapshot으로 최근60초를 표시하고 samples를 보내면 평균 없이 계속 이어진다.
- [ ] 53개 주소의 실제 값/unsupported/error를 구분한다. 단위 변환이 중복되지 않는다.
- [ ] normal → friction → friction+overload → normal에 맞춰 판정·구간·알림이 변한다.
- [ ] waiting/null/수신 단절에서 정상 복귀 또는 해제로 오인하지 않는다.
- [ ] 5분/전체를 조회하는 중 새 WS 샘플이 와도 누락·중복이 없다.
- [ ] 새로고침/재접속/새 실험 후 이전 세션 데이터가 섞이지 않는다.
- [ ] 종료 후 값이 더 생성되지 않고 로그 이력은 당시 진단·설정을 재현한다.
- [ ] 사용자 확인과 이상 해제는 독립적으로 동작한다.
- [ ] 실제 시작 요청 전에는 SDK로 모터를 제어하지 않는다.

참조 구현과 테스트: `mock_source.py`, `stream.py`, `tests/`, `frontend/src/services/telemetryAdapter.test.ts`, `frontend/e2e/`, `frontend/e2e-control/`.

기존 변환 완료 Sample 형식도 호환 처리하지만, 신규 수집 코드는 위 원시 registers 형식을 권장합니다. 프론트엔드의 TypeScript Sample은 정규화 후 내부 표현이므로 그 수십 개의 파생 필드를 백엔드에서 중복 계산할 필요가 없습니다.
