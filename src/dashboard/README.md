# 모터 대시보드 — 협업용 프로토타입

이 폴더는 백엔드, 프론트엔드, 가상 데이터 생성기, CSV 저장·조회, 실험 제어 복사본을 함께 담은 독립 실행 프로젝트입니다. 상위 `motor` 프로젝트나 `src` 폴더는 필요하지 않습니다. 폴더를 다른 위치로 이동하거나 이름을 바꿔도 `python main.py`로 실행할 수 있습니다.

협업자는 먼저 가상 모터로 화면을 확인한 뒤 [request.md](request.md)의 통신 계약에 맞춰 수집 코드와 진단 알고리즘을 연결하면 됩니다. 현재 화면에서 사용하는 대상은 XM430-W210 / XM430-W350입니다. 가상 데이터의 진단은 시나리오이며 실제 고장 탐지 알고리즘은 아닙니다.

## 1. 빠른 실행

필수: Python 3.11 이상. 검증 환경은 Python 3.14.5입니다. 프론트엔드를 새로 빌드할 때는 Node.js 22.12 이상이 필요합니다. Python·Node 자체는 전달 폴더에 포함하지 않습니다.

전달 ZIP은 `frontend/dist/`를 포함하므로 **화면 시연만 할 때는 Node.js 설치 없이** 실행할 수 있습니다. 의존성 최초 설치에는 인터넷이 필요합니다. 다른 컴퓨터의 `.venv`는 복사하지 마세요.

Windows PowerShell에서 압축을 푼 `dashboard` 폴더로 이동한 뒤:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe main.py
```

가상환경을 활성화해서 실행해도 됩니다.

```powershell
.\.venv\Scripts\Activate.ps1
python main.py
```

macOS/Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python main.py
```

브라우저에서 <http://127.0.0.1:8000>을 엽니다. 서버는 기본적으로 로컬 인터페이스에만 바인딩됩니다.

1. **제어** → 실행 대상 **가상 모터** 선택.
2. 모터 종류·ID·운동 조건 확인 → **설정 저장**.
3. **실험 시작** → 개요·모터·상세 분석에서 변화 확인.
4. **실험 종료** → 현재 왕복 완료 후 종료. 버튼 문구는 현재 실행 상태에 따라 바뀝니다.
5. **로그** → 종료된 실험의 **기록 분석**에서 저장한 전체 데이터 재생.

`main.py`만 켰을 때는 실험이 자동 시작되지 않습니다. 시작 전 빈 그래프는 정상입니다. 가상 모터는 COM 포트나 실제 장치 없이 동작합니다. 새 실험은 새 폴더와 runId를 만들고 기존 기록을 보존합니다.

## 2. 프론트엔드 빌드와 개발

소스만 전달받아 `frontend/dist/index.html`이 없다면 먼저 빌드합니다.

```powershell
cd frontend
npm ci
npm run build
cd ..
.\.venv\Scripts\python.exe main.py
```

개발 중에는 백엔드를 실행한 상태에서 별도 터미널로:

```powershell
cd frontend
npm run dev -- --open
```

Vite의 5173번 화면이 `/api`와 `/ws`를 8000번 백엔드로 전달합니다. 프론트만 수정했다면 `npm run build` 후 8000번 화면을 새로고침합니다. 백엔드 변경은 서버 재시작이 필요합니다. 서버 포트를 바꾸면 `config/dashboard.toml`과 `frontend/vite.config.ts`의 프록시도 함께 맞춥니다.

## 3. 페이지별 역할

| 페이지 | 표시·기능 |
|---|---|
| 개요 | 현재 측정값, 최근 60초 그래프, 모터 축 회전 표현, 진단 결과, 시작·종료 |
| 제어 | 설정 저장, 가상/실제 실행 요청, 왕복 완료 후 종료 |
| 모터 | 간접 주소·간접 데이터를 제외한 53개 Control Table 항목 |
| 상세 분석 | 60초·5분·10분·30분·1시간·전체, 측정값·추종 오차·상태 이력·이상 구간 목록 |
| 알림 | 전체·발생 중·해제됨·미확인·확인, 개별 확인, 사이드바 미확인 개수 |
| 로그 | 연·월·일별 실험 목록, 종료된 기록의 분석 |

기본 수집·화면 반영 주기는 0.1초입니다. 프론트엔드는 받은 측정값을 평균내지 않습니다. 개요는 최근 60초만 유지하고, 상세 분석의 긴 구간은 HTTP로 원본을 받은 뒤 WebSocket의 최신 샘플을 이어 붙입니다. `전체`는 실험이 길어질수록 브라우저 메모리가 증가합니다.

알림의 사용자 확인 여부는 브라우저 localStorage에 저장됩니다. CSV나 다른 브라우저로 전달되지 않습니다. 이상이 해제되어도 자동으로 사용자 확인 처리하지 않습니다.

## 4. 폴더 구조

```text
dashboard/
  main.py                     서버 실행 및 정적 웹 제공
  bootstrap.py                위치에 독립적인 Python 패키지 로딩
  settings.py                 기본 경로와 서버 설정
  routes.py / stream.py       HTTP API / WebSocket
  control.py / control_worker.py  실험 생명주기 / 실제 장치 전용 프로세스
  mock_source.py              가상 53개 원시 값과 진단 시나리오
  run_repository.py           실험 설정·목록·기록 관리
  history_archive.py          가상 데이터 CSV 기록·조회
  source_manager.py / csv_reader.py / normalize.py / history_query.py
                              기존 실험 CSV 호환 입력 경로
  experiment/                 독립된 모터 실험 코드 복사본
  config/                     기본 서버·실험·데모 설정
  frontend/
    src/                      Vue 3 + TypeScript + Pinia + ECharts 화면
    dist/                     main.py가 제공하는 빌드 결과
    package.json / package-lock.json
    e2e/ / e2e-control/        브라우저 검증
  contracts/examples.json     백엔드 구현에서 생성한 완전한 JSON 예시
  tools/
    package_dashboard.py      깨끗한 전달 ZIP 생성
    export_contract_examples.py  통신 예시 재생성
    demo_csv.py               선택적 CSV 입력 데모
  tests/                      실제 장치 없는 백엔드 검증
  requirements.txt            직접 Python 의존성 범위
  requirements.lock           검증용 고정 Python 의존성
  runtime/                    실행 중 만들어지는 설정·CSV·기록
  README.md / request.md      실행 안내 / 협업자 통합 계약
```

## 5. 저장 구조

기본 설정에서는 생성 파일이 이 폴더 밖으로 나가지 않습니다.

```text
runtime/
  control/
    saved.json
    configurations/<configId>.toml
  mock_runs/YYYY/MM/DD/<시각>_<runId>/
    config.toml
    metadata.json
    telemetry.csv
  experiment_runs/YYYY/MM/DD/<시각>_<runId>/
    config.toml
    metadata.json
    motor_metadata.json
    telemetry.csv
    result.json
  standalone_runs/<모터>/<조건>/   터미널 직접 실행 복사본의 CSV
  current_experiment.json          현재 실제 실험 CSV 안내
  demo/                           선택적 CSV 데모
```

날짜별 실험 폴더는 한국 시간 기준입니다. DB는 사용하지 않습니다. 제어 화면에서 시작한 실행은 `mock_runs` 또는 `experiment_runs`에 저장되고 로그에서 조회됩니다. `experiment/repeated_cycle.py`를 직접 실행한 CSV는 `standalone_runs`에 저장되며, 이 호환 경로의 기록은 자동으로 로그 목록에 등록되지 않습니다.

설정 파일의 상대 경로는 설정 파일 위치 기준입니다. 기존 외부 CSV를 계속 연결하려면 `data_root`와 안내 파일을 명시적으로 설정합니다. 이전 `results/raw` 기록을 자동 이동하거나 삭제하지 않습니다.

## 6. 협업 연결 지점

[request.md](request.md)를 먼저 읽어 주세요. 권장 입력은 **원시 레지스터 + 식별자·시간 + 알고리즘 판정**입니다. 프론트에서 단위 변환·차트용 추종 오차를 계산합니다. 모터 제어, 측정, 고장 판정, 영구 저장은 협업자의 백엔드 책임입니다.

- 실시간: `/ws/telemetry`.
- 긴 구간: `/api/history`.
- 제어: `/api/control` 및 config/start/stop.
- 과거 기록: `/api/runs` 및 상세·history.
- 스키마의 TypeScript 원본: `frontend/src/types/motor.ts`.
- 주소 정의·단위: `frontend/src/services/controlTable.ts`, `analysis.ts`.
- 수신 어댑터: `frontend/src/services/telemetryAdapter.ts`.

백엔드 내부 저장 방식은 CSV에 고정될 필요가 없습니다. 위 API 계약을 유지하면 동일 화면을 사용할 수 있습니다. 실제 수집 복사본은 53개 전체와 사용자 알고리즘을 구현한 완성본이 아니므로 협업자의 수집·판정 코드로 연결해야 합니다.

## 7. 테스트

`dashboard` 폴더에서:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
cd frontend
npm ci
npm test
npm run build
npx playwright install chromium
npm run test:e2e
npx playwright test --config=playwright.control.config.ts
```

브라우저 테스트는 `dashboard/.venv`의 Python을 우선 사용합니다. 기존 공용 환경을 사용한다면 `$env:DASHBOARD_PYTHON = '사용할 python.exe의 절대 경로'`를 지정합니다. 테스트 서버는 8765/8766 포트와 임시 데이터 폴더를 사용하며 실제 모터를 구동하지 않습니다.

검증 결과와 범위는 [VALIDATION.md](VALIDATION.md)에 정리했습니다.

## 8. 전달용 ZIP 만들기

```powershell
cd frontend
npm run build
cd ..
.\.venv\Scripts\python.exe tools/package_dashboard.py
```

출력: `runtime/handoff/dashboard-날짜-시간.zip`.

ZIP에는 `dashboard/` 폴더 아래 코드·문서·계약 예시·프론트 빌드를 포함합니다. 기존 실험 CSV, 저장된 장치 설정, 가상환경, node_modules, 테스트 화면, 캐시는 제외합니다. 원본 작업 폴더의 기록은 그대로 보존합니다. 동일 출력 파일을 덮어쓰지 않습니다.

Git으로 전달하면 `frontend/dist`는 기본 ignore 대상이므로 받는 쪽에서 빌드해야 합니다. ZIP 전달은 빌드까지 포함하므로 Python 의존성 설치만으로 시연할 수 있습니다.

## 9. 현재 범위와 주의점

- 단일 서버 프로세스와 단일 실행 제어 기준입니다. 여러 worker로 실행하지 않습니다.
- 모터 테이블의 RW는 레지스터 특성 표시이며 모든 주소 쓰기 UI를 제공한다는 뜻이 아닙니다.
- 실제 SDK 접근은 실제 모터 시작 요청 후 별도 worker에서 수행합니다. 가상 모터 실행에는 장치 접근이 없습니다.
- 정상 종료는 현재 왕복 완료 후 토크 유지입니다. UI 종료 버튼은 비상 정지 기능이 아닙니다. 실제 통합 시 통신 단절·장치 오류·프로세스 강제 종료 정책은 별도 설계가 필요합니다.
- 로그인·권한 기능이 없는 로컬 연구용 프로토타입입니다. 현재 포트와 SSH 포워딩 사용 범위에서 시연합니다.
- 실제 장치에서의 통합 검증은 협업자의 수집·제어 연결 후 진행해야 합니다.
- 기존 `CONTROL.md`, `HISTORY.md`, `MOCK_BACKEND.md` 등은 세부 구현 이력입니다. 실행 방법과 통합 기준은 이 README와 request.md를 우선합니다.
