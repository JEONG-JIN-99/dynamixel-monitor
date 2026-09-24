# 제어와 실험 기록

## 사용 순서

1. main.py를 실행하고 웹 화면의 **제어**로 이동한다. 서버 시작만으로 실험이나 CSV 저장이 시작되지 않는다.
2. 실행 대상(가상 모터/실제 모터), 모델·ID·통신 포트, 왕복 조건·수집 주기·실험 조건을 지정하고 **설정 저장**을 누른다.
3. **실험 시작**을 누른다. 개요의 시작 버튼도 같은 저장 설정을 사용한다. 새 runId와 경과 시간 0초, 새 실행 폴더를 만든다.
4. **실험 종료**를 누르면 현재 상승→상단 대기→복귀→하단 대기를 끝낸 뒤 종료한다. 화면의 '종료 대기' 동안 수집/저장은 계속된다. 준비 중 종료하면 새 왕복을 시작하지 않는다.
5. **로그**에서 년/월/일 및 실행 대상을 선택하고 **기록 보기**를 누른다. 기본 범위는 전체이고 기존 상세분석의 8개 그래프와 상태 이력을 재사용한다.

정상 종료 시 토크를 해제하지 않는다. 실제 실험 복사본의 기존 초기 설정 과정에서는 제어 모드 변경을 위해 토크 OFF/ON이 수행된다. 통신 오류 시에는 기존 코드의 현재 위치 유지 처리를 시도한다. 실험 조건은 기록용 분류이며, 조건 선택 자체가 전압이나 마찰 등의 물리적 고장을 발생시키지는 않는다.

페이지 이동·브라우저 닫기·새로고침은 실행에 영향을 주지 않는다. 실행 중 설정 저장과 중복 시작은 서버에서도 차단한다. 종료 요청의 runId가 현재 실행과 다르면 409로 거절한다. 서버의 정상 종료는 관리 중인 실험에도 왕복 완료 후 종료를 요청한다. 독립 터미널에서 실행한 실험은 서버 종료 대상이 아니다.

## 저장 위치

```text
src/dashboard/runtime/
  control/
    saved.json                       # 마지막 저장 설정
    configurations/<설정ID>.toml
    controller.lock                  # 관리 서버 중복 실행 방지
  mock_runs/YYYY/MM/DD/<시각>_<runId>/
    config.toml
    metadata.json
    telemetry.csv
  experiment_runs/YYYY/MM/DD/<시각>_<runId>/
    config.toml
    metadata.json
    telemetry.csv
    motor_metadata.json              # 실험 복사본이 기록한 모델·설정
    runner.log                       # 장치 실행 프로세스 출력
    result.json                      # 종료 코드·완료 왕복 수
    stop.request                     # 종료 요청 시 생성
```

날짜는 시작 시각의 한국 시간 기준이며 자정을 넘어도 같은 폴더를 쓴다. 저장 설정 변경은 과거 config.toml에 영향을 주지 않는다. 두 기록 루트는 분리하며 기존 results/raw와 src/experiment는 변경하지 않는다. 기존 날짜 없는 MOCK 폴더와 터미널 실험 CSV는 보존하지만 이번 로그 목록에 자동 편입하지 않는다. DB는 사용하지 않는다.

metadata.json의 schemaVersion은 2다. 실행 식별자, source, 시작/종료, 상태, 종료 사유, 설정 사본/ID, 모델/ID, 행 수/마지막 순번/경과 시각/완료 횟수를 저장한다. 임시 JSON을 교체해 원자적으로 갱신한다. MOCK CSV는 53개 원시 레지스터와 수신 판정을 보존한다. 실제 CSV는 기존 실험 v4 형식의 12개 상태값 및 명령·설정 기록을 유지한다. 실제 알고리즘 판정은 아직 실험 복사본에 없으므로 만들어 넣지 않는다.

강제 종료로 남은 실행은 다음 시작 때 중단으로 복구하며, 현재 실험 잠금을 가진 실제 worker가 살아 있으면 그 runId를 다시 관리한다. 복구된 worker의 종료 요청은 stop.request로 전달한다. 완료된 기록은 현재 서버 세션이나 실행과 독립적으로 다시 읽는다.

## API

| 요청 | 동작 |
|---|---|
| GET /api/control | defaults, saved, run, active, externalActive |
| POST /api/control/config | `{source: "mock" 또는 "real", config: ExperimentConfig 전체 객체}` 검증·TOML 저장 |
| POST /api/control/start | `{configId}` 실행 시작 |
| POST /api/control/stop | `{runId}` 현재 왕복 후 종료 예약 |
| GET /api/runs | year/month/day/source, offset, limit으로 목록 필터·페이지 조회 |
| GET /api/runs/{runId} | 당시 설정과 기록 metadata |
| GET /api/runs/{runId}/history?durationSec=0 | 완료/오류/중단 기록의 원본 측정 프레임 |

기간 값은 60/300/600/1800/3600/0(전체)이다. 유한 구간은 기록 마지막 시각 기준이다. 기록 조회에 임의 파일 경로를 받지 않는다. 실행 중인 실험의 긴 구간 조회는 기존 /api/history를 사용한다.

브라우저의 조회 소스 `mock/csv`와 제어의 실행 대상 `mock/real`을 구분한다. 시작 후 화면은 해당 소스로 이동한다. URL 소스 선택만으로 실험을 실행하거나 멈추지는 않는다. SDK import와 COM 접근은 실제 시작 시 생성하는 control_worker.py에만 있다. worker는 현재 Python 환경 경로를 전달받으므로 기본 Python+site-packages 우회 실행도 지원한다.

## 검증

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
cd frontend
npm test
npm run build
npm run test:e2e
npx playwright test --config=playwright.control.config.ts
```

제어 전용 브라우저 검사는 별도 임시 폴더와 8766 포트를 사용한다. 가상 모터 실행과 가짜 SDK 장치만 사용하며 실제 장치는 구동하지 않는다. 테스트 전용 mock_prehistory_ms를 명시한 앱만 자동 합성 이력을 시작한다. 운영 main.py는 이를 전달하지 않는다.
