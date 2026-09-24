# 백엔드 MOCK과 협업 전송 계약

## 실행과 확인

```powershell
cd <dashboard 폴더 경로>
.\.venv\Scripts\python.exe main.py
```

기존 main.py가 실행 중이면 Ctrl+C로 종료한 뒤 다시 실행한다. [가상 데이터 화면](http://127.0.0.1:8000/?source=mock)에서 Ctrl+F5로 새로고침한다. 제어에서 실행 대상을 가상 모터로 선택하고 설정 저장 → 실험 시작을 누른다. 서버 실행만으로 가상값을 만들지 않는다. 실제 실험이나 모터 연결은 필요 없다. 개발용 Vite를 사용해도 백엔드가 필요하며 `/ws` 프록시는 기존 설정을 그대로 사용한다.

```text
mock_source.py (53개 원시 주소값 + 진단 시나리오)
 → TelemetryHub (공유 60초 버퍼)
 → /ws/telemetry?source=mock
 → motorDataService.ts (WebSocket 수신)
 → telemetryAdapter.ts (원시값 부호·단위 변환)
 → motorStore.ts (60초 이력)
 → 개요 / 모터 / 상세 분석
```

프론트엔드의 motorMock.ts와 registerMock.ts 생성기는 제거했다. 서버 연결이 없으면 가상값을 생성하거나 다른 소스로 자동 전환하지 않는다. 소켓 종료 시 마지막 수신값을 유지하고 연결 대기를 표시한다. 재연결은 0.5초에서 최대 10초까지 간격을 늘려 시도하며 새 snapshot으로 동기화한다.

MOCK은 설정한 수집 주기(기본 0.1초)마다 서버에서 생성한다. 모델/ID, 회전수·방향, 가속 시간·이동 시간·대기·왕복 횟수를 저장 설정에서 적용한다. 서버 하나의 생성기와 실행 ID를 여러 브라우저가 공유한다. 일반 실행은 0초부터 기록하고 최근 60초 버퍼를 채운다. 같은 프레임을 runtime/mock_runs의 전용 CSV에 저장한 뒤 전송한다. 상세분석은 기록 API로 5분~전체 원본을 조회할 수 있다. 계약과 저장 방식은 [HISTORY.md](HISTORY.md)를 참고한다. 실시간 전송 지연이 생기면 경과 시각에 공백이 생길 수 있으며 프론트엔드가 임의로 샘플을 보충하지 않는다.

정상 → 마찰 → 과부하를 반복하는 진단 예시를 서버가 보낸다. 이는 실제 고장이나 학습된 문제 탐지 알고리즘의 결과가 아니다. 전류·오차와 함께 화면 표시를 검증하기 위한 시나리오다.

## 협업자가 구현할 데이터

계산된 position/current나 추종 오차를 중복 전송할 필요 없다. `src/dashboard/mock_source.py`의 `sample()`이 실제 전송 예제다. 프론트엔드 타입은 `frontend/src/types/motor.ts`의 `RegisterSample`, `Message<RegisterSample>`을 기준으로 한다.

한 샘플의 구조:

```json
{
  "serverSessionId": "server-unique-id",
  "sourceSessionId": "acquisition-unique-id",
  "runId": "run-unique-id",
  "busId": "bus-1",
  "seq": 1,
  "id": 1,
  "model": "XM430-W210",
  "elapsedMs": 0,
  "timestamp": 1790000000000,
  "receivedAt": 1790000000000,
  "registers": {
    "11": { "raw": 4, "receivedAt": 1790000000000, "status": "received" },
    "126": { "raw": 100, "receivedAt": 1790000000000, "status": "received" },
    "132": { "raw": 1010, "receivedAt": 1790000000000, "status": "received" },
    "140": { "raw": 1000, "receivedAt": 1790000000000, "status": "received" }
  },
  "diagnosis": { "state": "normal", "codes": [] }
}
```

주소값은 설명을 위해 4개만 발췌했다. 실제 MOCK은 간접 주소를 제외한 53개를 모두 보낸다. `raw`는 레지스터 원시 정수이며 표시 단위로 변환한 소수가 아니다. `receivedAt`은 해당 주소의 측정 시각(ms)이다. 같은 수집 프레임의 값은 동일 시각을 사용한다. 부호 있는 항목은 음의 정수 또는 unsigned 2의 보수 정수를 모두 허용한다.

- `timestamp`: 모터 샘플의 측정 시각, Unix milliseconds.
- `elapsedMs`: 실행 시작부터 측정 경과 ms. 시간은 뒤로 가지 않아야 한다.
- `seq`: 스트림 전체에서 증가하는 샘플 순번. 여러 모터를 보내도 전역적으로 증가시킨다.
- `serverSessionId`: 서버 재시작 시 새 값. `sourceSessionId`: 수집 소스/실행 변경 시 새 값.
- 미수신: 주소 생략. 오류: `raw:null,status:"error"`. 미지원: `raw:null,status:"unsupported"`. 필요 시 `error` 문자열 추가.
- 설정을 매번 보내지 않으면 snapshot/system의 해당 모터 metadata.registers에 최신 설정을 보관해서 제공한다. 실시간 측정값을 이전 값으로 채워 새 샘플처럼 보내지 않는다.
- 알고리즘 미수신: diagnosis 생략 또는 null. 정상: state=normal,codes=[]. 이상: state=fault,codes=["friction"]처럼 제공한다. 프론트엔드가 오류 비트나 전류 크기로 진단 결과를 생성하지 않는다.
- 위치 추종 오차는 동작 모드 3/4/5, 속도 추종 오차는 1/3/4/5이고 측정 시각이 맞을 때 프론트엔드에서 계산한다.

## WebSocket 메시지 순서

현재 서버 연결 계층을 그대로 사용할 때의 규칙이다. 모든 메시지는 `schemaVersion:1`, `serverSessionId`, `sourceSessionId`를 포함한다.

1. 연결 직후 `type:"snapshot"`: `MockSource.snapshot()` 구조의 전체 초기 상태. history, latest, runId, experiment, metadata, system, retentionSec=60, capacity, seq, events를 포함한다. 처음 수집을 시작하면 history=[],latest=null로 보낼 수 있다.
2. 이후 `type:"samples", samples:[샘플...]`: 새 측정값을 전송한다. 최초 snapshot과 샘플의 세션·실행 ID가 같아야 한다.
3. 연결/설정 정보 변경은 `type:"system", system, experiment, metadata`로 보낸다.
4. 실행 변경과 이력 재동기화는 snapshot과 동일한 구조의 `type:"reset"`으로 보낸다.

MOCK 주소는 `/ws/telemetry?source=mock`, 기존 실제 입력 주소는 `/ws/telemetry`이다. 두 소스는 버퍼와 구독이 분리되며 소스 선택은 다른 브라우저에 영향을 주지 않는다. 잘못된 source는 연결을 거부한다. 실제 수집기로 바꿀 때 동일 계약을 제공하면 화면 컴포넌트를 변경할 필요가 없다. endpoint나 envelope를 바꾸면 `motorDataService.ts` 연결 어댑터를 수정하면 된다.

## 파일과 검증

- `mock_source.py`: 백엔드 생성기, 원시 주소값, 예시 진단, 60초 버퍼.
- `main.py`: 서버 시작/종료에 생성기를 함께 관리.
- `routes.py`: 쿼리로 스트림 선택, 구독 정리.
- `frontend/src/services/telemetryAdapter.ts`: 실데이터와 가상 데이터가 공유하는 변환 경계.
- `tests/test_mock_source.py`: 53개 주소, 원시값만 전송, 버퍼 경계, 동일 서버 스트림 공유와 소스 분리.
- `frontend/e2e/dashboard.spec.ts`: 실제 백엔드 raw-only 메시지로 개요·53개 표·계산 그래프를 검증하고 소켓 종료 시 값이 멈추는지 검증.

백엔드 MOCK으로 확인하는 것은 전송 계약과 표시 동작이다. 실제 모터 수집 코드나 알고리즘의 탐지 정확도가 검증되는 것은 아니다.
