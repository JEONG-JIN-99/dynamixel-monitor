# dynamixel-monitor

PC → U2D2 → DYNAMIXEL 구성으로 모터에 직접 명령을 보내고 CSV를 수집합니다.
지원 모델은 XM430-W210, XM430-W350, XL430-W250입니다.
기본 터미널 실험은 설정한 모델 한 대를 실행당 제어합니다.
웹 기반 [대시보드 V2](src/dashboard_v2/README.md)는 8개 모터의 상태 표시와 독립 실험 관리를 제공합니다.

## 폴더 구성

```text
motor/
├── config/
│   └── experiment.toml        # 실험 전에 수정하는 설정
├── src/experiment/
│   ├── repeated_cycle.py     # 반복 왕복 실행
│   ├── configuration.py      # 설정 검증과 모델별 정보
│   └── acquisition.py        # 공통 모터 제어·데이터 기록
├── src/dashboard/            # 기존 단일 모터 대시보드 (8000번 포트)
├── src/dashboard_v2/         # 8개 모터 대시보드·독립 실행 및 협업 연결 (8001번 포트)
├── results/
│   ├── raw/
│   │   ├── XM430-W210/       # 아래에 normal/, overload_0.5kg/ 등 조건 폴더
│   │   ├── XM430-W350/
│   │   └── XL430-W250/       # 해당 모델·조건으로 실행 시 생성
│   └── legacy/               # 이전 측정 CSV 보관
├── tests/                    # 장치 없이 실행하는 검증
├── 3d_design/                # 기구 설계 자료
├── requirements.txt
├── .gitignore
└── README.md
```

## 설치

Python 3.11 이상을 사용합니다(TOML 읽기용 표준 라이브러리 사용).
프로젝트 루트의 PowerShell에서 실행합니다. 기존 실험과 대시보드는 루트 `.venv` 하나를 공용으로 사용합니다:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

이미 가상환경이 있으면 생성 단계는 생략하고 본인의 환경을 활성화하세요.
가상환경 이름이나 경로가 다르면 활성화 경로를 맞춰 주세요. 이후 명령은 활성화된 터미널에서 실행합니다.
확인한 로컬 환경은 Python 3.14.5, pyserial 3.5, dynamixel-sdk 4.0.5입니다.

## CSV 대시보드 실행

루트 가상환경을 활성화한 터미널에서 실행합니다. 루트 requirements.txt가 대시보드의 검증된 웹 서버·테스트 의존성도 설치합니다.

```powershell
python .\src\dashboard\main.py
```

[http://127.0.0.1:8000](http://127.0.0.1:8000)에서 화면을 봅니다. 실제 실험은 별도 터미널에서 같은 루트 가상환경을 활성화한 뒤 아래 복사본으로 실행합니다.

```powershell
python .\src\dashboard\experiment\repeated_cycle.py
```

복사본 설정·CSV 경로·Frontend 빌드와 데모 실행은 [대시보드 안내](src/dashboard/README.md)를 참고하세요. 원본 실험 소스와 설정은 유지되며 Python 환경만 공유합니다.


## 대시보드 V2 — 8개 모터 제어·모니터링

`src/dashboard_v2`는 백엔드, 프론트엔드, 가상 데이터 생성기, 실험 코드 복사본을 담은 독립 프로젝트입니다. 현재 모터 1·2는 실제/가상 모터를 선택하고, 모터 3~8은 서로 다른 가상 시나리오로 시연합니다. 지원 화면 모델은 XM430-W210 / XM430-W350입니다.

- **개요:** 기본 3D 로봇과 2D 도면 전환, 모터 1~8의 위치·상태·시작/종료. 모터별 개요에서는 측정값과 최근 60초 그래프를 표시합니다.
- **제어:** 모터별 설정 저장과 독립 실행. 종료 요청은 현재 왕복을 마친 뒤 적용하며 실제 모터의 토크를 유지합니다.
- **모터·상세 분석:** 53개 레지스터 표시, 60초부터 전체 실험까지 구간 선택, 진단 결과와 이상 구간 표시.
- **알림·로그:** 모터별 이상 알림·전체 확인, 날짜별 실험 기록과 과거 분석.

루트의 기존 `.venv`를 그대로 사용할 수 있습니다. Git으로 처음 받은 경우 Python 의존성을 설치하고 프론트엔드를 빌드합니다(Node.js 22.12 이상 필요).

```powershell
# 프로젝트 루트에서 실행. .venv가 없다면 먼저 python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\src\dashboard_v2\requirements.lock
npm --prefix .\src\dashboard_v2\frontend ci
npm --prefix .\src\dashboard_v2\frontend run build
.\.venv\Scripts\python.exe .\src\dashboard_v2\main.py
```

[http://127.0.0.1:8001](http://127.0.0.1:8001)에 접속합니다. 서버 실행만으로 실험이 시작되지는 않습니다. 장치 없이 확인하려면 **제어 → 모터 1 → 가상 모터 → 설정 저장 → 실험 시작**을 선택하거나, 개요에서 모터 3~8의 준비된 가상 설정으로 시작합니다. 한 모터만 실행해도 됩니다.

V2 내부는 `backend/`와 `frontend/`로 구분합니다. 백엔드는 API(`api`), 제어(`control`), 실험 절차(`experiment`), 실제·가상 연결(`adapters`), 실시간 데이터(`telemetry`), 저장(`storage`)으로 나뉩니다. 최상위 `main.py`가 서버를 실행하며 설정과 기록은 기존 `config/`, `runtime/`에 유지합니다.

로컬 빌드와 의존성이 이미 준비되어 있으면 마지막 `main.py` 실행 명령만 사용하면 됩니다. `runtime/`의 실험 기록·저장 설정, `.venv`, `node_modules`, `frontend/dist`는 로컬에 유지하고 Git에서는 제외합니다. 새로 복제한 환경에는 기존 실험 기록이 없으며 위 설치·빌드가 필요합니다. 전달용 ZIP에는 빌드 결과가 포함됩니다.

협업자는 측정 레지스터·진단 결과 및 제어/이력 API를 연결합니다. 실제 실험 방식을 바꾸어도 MOCK의 동작 로직이 자동 변경되는 것은 아니며, 제어 화면과 가상 시나리오도 필요에 따라 맞춰야 합니다. 기존 원본 실험과 V1은 별도로 유지됩니다.

- [V2 실행·개발 안내](src/dashboard_v2/README.md)
- [협업자 연결 명세 및 데이터 형식](src/dashboard_v2/request.md)
- [검증 범위와 결과](src/dashboard_v2/VALIDATION.md)

## 실험 설정

코드 대신 [config/experiment.toml](config/experiment.toml)을 수정하세요.
주요 설정 예시는 다음과 같습니다.

```toml
[motor]
name = "XM430-W210"
port = "COM5"
baudrate = 1000000
id = 1
protocol_version = 2.0

[experiment]
turns = 1.0
direction = 1
acceleration_ms = 2000
profile_duration_ms = 6000
top_dwell_sec = 1.0
bottom_dwell_sec = 1.0
max_cycles = 0
```

위 예시는 주요 부분만 보여줍니다. 실제 파일의 `[condition]`, `[logging]`, `[control]`도 유지하세요.

- W350 실험: `name = "XM430-W350"`로 변경합니다.
- XL 실험: `name = "XL430-W250"`로 변경합니다.
- `port`, `baudrate`, `id`는 연결된 U2D2와 모터에 맞춥니다.
  이 값들은 PC의 접속 대상 설정이며 모터에 저장된 ID나 통신 속도를 바꾸지는 않습니다.
- `turns`는 양수 회전수, `direction`은 `1` 또는 `-1`입니다.
- 가속 시간과 감속 시간은 같으며, 두 시간의 합이 전체 이동 시간을 넘을 수 없습니다.
- `max_cycles = 0`은 q 입력까지 반복, 양수는 지정한 왕복 횟수만 수행합니다.
  한 번만 왕복하고 종료하려면 `max_cycles = 1`로 설정합니다.
- `[logging]`에서 수집 주기, 화면 출력 주기, 파일 버퍼 저장 주기를 바꿉니다.
- `[control]`에서 이동 제한 시간, 위치 허용 오차, 정상 종료 시 토크 해제를 설정합니다.
- 설정은 시작할 때 한 번 읽습니다. 실행 중 수정한 값은 다음 실행부터 적용됩니다.

현재 기본값은 1회전, 이동 6초(가속 2초·등속 2초·감속 2초), 상·하단 대기 각각 1초입니다.
샘플링은 목표 0.1초 주기이며 통신 지연에 따라 실제 간격은 달라질 수 있습니다.

## 실험 조건

`[condition]`은 데이터 분류와 기록을 위한 설정이며 전압·전류·부하를 자동으로 변경하지 않습니다.

| 실험 조건 | `name` 값 | 저장 폴더 |
| --- | --- | --- |
| 정상 | `normal` | `normal/` |
| 과전압 | `overvoltage` | `overvoltage/` |
| 과소전압 | `undervoltage` | `undervoltage/` |
| 과부하 | `overload` | `overload_<부하량>kg/` |
| 과소전류 | `undercurrent` | `undercurrent/` |
| 마찰 | `friction` | `friction/` |
| 기어 백래시 | `gear_backlash` | `gear_backlash/` |

0.5 kg 과부하 실험의 설정 예시:

```toml
[condition]
name = "overload"
load_kg = 0.5
```

`load_kg`는 정해진 목록 없이 kg 단위의 양수 부하량을 입력합니다. `0.75`는 `overload_0.75kg/`,
`1.5`는 `overload_1.5kg/`로 저장됩니다. `1`과 `1.0`은 같은 폴더를 사용합니다.
과부하 이외의 조건에서는 `load_kg = 0`으로 설정하고 조건 이름만 폴더명으로 사용합니다.
기존 조건 미분류 로그는 그대로 보존하며, 새 실행부터 조건 폴더를 사용합니다.

## 실행

본인의 가상환경을 활성화한 뒤 프로젝트 루트에서 실행합니다. 새 터미널을 열었다면 가상환경을 다시 활성화하세요.

모터에 연결하지 않고 설정만 확인:

```powershell
python src\experiment\repeated_cycle.py --check-config
```

반복 왕복 실험:

```powershell
python src\experiment\repeated_cycle.py
```

현재 위치를 기준으로 설정한 회전수만큼 이동 → 상단 대기 → 기준 위치 복귀 → 하단 대기를 반복합니다.
`q` 입력 후 Enter를 누르면 현재 왕복과 하단 대기를 마친 뒤 종료합니다.

`q`는 종료 예약입니다. 상승 중 입력해도 목표 위치까지 이동하고 상단 대기,
기준 위치 복귀, 하단 대기를 마친 뒤 데이터를 저장하고 종료합니다.
여기서 기준 위치는 이번 실행 시작 시 읽은 위치이며, 절대 위치 0을 뜻하지 않습니다.
통신 오류나 Ctrl+C로 중단하면 정상 복귀 대신 현재 위치 유지 명령을 시도합니다.

다른 설정 파일을 선택할 수도 있습니다.

```powershell
python src\experiment\repeated_cycle.py --config config\w350.toml
```

이 예시는 `experiment.toml`을 `w350.toml`로 복사해서 수정한 경우입니다.
기본 설정·데이터 경로는 실행 위치와 무관하게 프로젝트 기준입니다.
직접 전달하는 상대 `--config` 경로는 현재 실행 폴더 기준입니다.

## 모터 연결 확인과 종료

동작 전에 ping에서 얻은 모델 번호와 설정한 모터 이름을 비교합니다.
다르면 모터 제어 설정을 쓰기 전에 중단합니다.
시간 기반 프로파일에 필요한 펌웨어 버전 42 이상도 확인합니다.
모터의 운전 모드는 다회전 위치 제어(Extended Position Control Mode)를 사용합니다.
XM에서 전류를 기록하지만 전류 제어 모드로 바꾸지는 않습니다.

기본적으로 정상 종료 후에도 토크를 유지합니다.
`torque_off_on_normal_exit = true`이면 정상 종료 때만 토크를 해제합니다.
Ctrl+C, 통신 오류, 하드웨어 오류, 이동 시간 초과 발생 시
현재 위치 유지 명령을 시도하고 포트를 닫습니다.
통신이 끊긴 경우 위치 유지 명령의 성공을 보장할 수 없습니다.

## 데이터 저장

모터 이름과 실험 조건에 따라 자동으로 분리합니다.

```text
results/raw/XM430-W210/normal/XM430-W210_normal_날짜_시간.csv
results/raw/XM430-W210/normal/XM430-W210_normal_날짜_시간.json
results/raw/XM430-W350/overload_0.5kg/XM430-W350_overload_0.5kg_날짜_시간.csv
results/raw/XM430-W350/overload_0.5kg/XM430-W350_overload_0.5kg_날짜_시간.json
```

실행당 CSV 하나와 같은 이름의 JSON 하나를 저장합니다.
파일명은 `<모터 이름>_<실험 조건>_YYYYMMDD_HHMMSS_ffffff`이며 마지막 6자리는 마이크로초입니다.
실험 조건을 파일명에도 넣어 폴더 없이 전달해도 구분할 수 있습니다. 과부하는 부하량도 포함합니다.
JSON에는 실행 당시 전체 설정, 모델 번호, 펌웨어 버전, 전류/부하 환산 정보를 보관합니다.
CSV의 `Condition`과 JSON의 `condition`에도 폴더명과 같은 실험 조건을 기록합니다.
CSV의 `Load [kg]`는 설정에 입력한 과부하 실험의 부하량이며, 다른 조건에서는 비워 둡니다.
이 부하량은 모터가 측정한 값이 아니며 `Present Load`와 구분합니다.
나중에 설정 파일을 수정해도 이전 실험 조건을 확인할 수 있습니다.
오류로 중단된 실행에는 일부 데이터 또는 헤더만 저장될 수 있습니다.

| 모터 | 주소 126의 CSV 원시값 열 | 환산값 열 |
| --- | --- | --- |
| XM430-W210 / XM430-W350 | `Present Current` | `Present Current [mA]` = 원시값 × 2.69 |
| XL430-W250 | `Present Load` | `Present Load [%]` = 원시값 × 0.1 |

전류/부하는 signed 2-byte로 해석하므로 음수 부호도 보존합니다.
나머지 모터 상태 열은 원시값입니다. 위치는 pulse, 속도는 0.229 rpm 단위,
입력 전압은 0.1 V 단위입니다.
공통 메타데이터에 모델명, 모터 ID, 실험 종류, 왕복 횟수, 구간, 회전수,
기준·목표 위치, 프로파일 설정을 저장합니다.
새 CSV는 기존 로그보다 열이 늘어났으므로 이전 분석 코드의 열 이름을 확인하세요.

## 실험 결과 항목 설명

CSV의 한 행은 한 번 수집한 상태입니다. 현재 모델별 CSV에는 총 27개 열이 들어갑니다.
XM은 전류 열, XL은 부하 열을 사용하므로 아래 표의 모든 모델별 열이 한 파일에 함께 나오지는 않습니다.

### 실험 정보와 설정값

아래 값들은 프로그램이 기록한 정보이며, 모터에서 측정한 상태값과 구분합니다.

| CSV 열 이름 | 의미 및 단위 |
| --- | --- |
| `PC Time` | 데이터를 기록한 PC의 로컬 날짜·시각. 밀리초까지 표시합니다. |
| `Elapsed Time [s]` | 모터 초기 설정을 마치고 데이터 수집을 시작한 이후 경과 시간 [초]. |
| `Motor Model` | 설정한 모터 이름. 예: `XM430-W210`. |
| `Motor ID` | 통신 대상 모터 ID. |
| `Experiment` | 반복 왕복 실험을 뜻하는 `cycle`. |
| `Condition` | 실험 조건. 예: `normal`, `overload_0.5kg`. |
| `Load [kg]` | 과부하 실험에서 사용자가 입력한 부하량 [kg]. 다른 조건은 빈칸이며 모터 측정값이 아닙니다. |
| `Cycle` | 왕복 번호. 1부터 증가합니다. |
| `Phase` | 현재 이동·대기 구간. 아래 구간 표를 참고하세요. |
| `Target Turns` | 설정한 이동 방향 × 회전수. 복귀 구간에서도 같은 설정값이며, 누적 회전수나 순간 이동 방향이 아닙니다. |
| `Base Position` | 토크를 켠 뒤 읽은 이번 실험의 기준 위치 [pulse]. 반복 실험의 복귀 위치입니다. |
| `Goal Position` | 해당 구간에서 모터에 명령한 목표 위치 [pulse]. 공식 주소 116의 명칭을 사용합니다. |
| `Profile Acceleration` | 모터에 설정한 가속 시간 [ms]. 시간 기반 모드이므로 가속도의 물리 단위가 아닙니다. 공식 주소 108. |
| `Profile Velocity` | 모터에 설정한 전체 이동 프로파일 시간 [ms]. 시간 기반 모드이므로 rpm 값이 아닙니다. 공식 주소 112. |

목표 위치와 프로파일 열은 명령·설정한 값을 기록합니다. 매 샘플마다 해당 설정을 모터에서 다시 읽는 값은 아닙니다.
위치 1회전은 4096 pulse이며, 상대 이동 각도는 `(Present Position - Base Position) × 360 / 4096`으로 계산할 수 있습니다.
시간 기반 프로파일의 단위는 [공식 Profile 설명](https://emanual.robotis.com/docs/en/dxl/x/xm430-w210/#profile-acceleration108)을 따릅니다.

### 모터에서 읽은 상태값

열 이름은 공식 Control Table 명칭이며, CSV에는 부호를 해석한 원시값을 저장합니다.
아래 환산식은 분석할 때 사용하는 식입니다. 별도 환산 열은 전류 또는 부하에만 생성합니다.

| CSV 열 이름 | 주소 | 의미 및 해석 |
| --- | ---: | --- |
| `Hardware Error Status` | 70 | 하드웨어 오류를 나타내는 비트 조합. 0이면 보고된 오류 없음, 0이 아니면 오류 비트를 확인합니다. |
| `Realtime Tick` | 120 | 모터 내부 시간 [ms]. 32767 다음에 0으로 돌아가므로 실험 전체 경과 시간과 다릅니다. |
| `Moving` | 122 | 모터의 움직임 판정 플래그(0 또는 1). 단독으로 목표 위치 도착을 뜻하지는 않습니다. |
| `Moving Status` | 123 | 도착 여부, 프로파일 진행 상태 등을 담은 비트 조합. 단순한 참/거짓 값이 아닙니다. |
| `Present PWM` | 124 | 현재 PWM 출력 원시값. 약 `원시값 × 0.113`으로 % 환산합니다. |
| `Present Current` | 126 | XM 전용 현재 전류 원시값. `원시값 × 2.69`로 mA 환산합니다. 음수 부호도 보존합니다. |
| `Present Load` | 126 | XL 전용 부하 추정 원시값. `원시값 × 0.1`로 % 환산합니다. 무게나 토크를 직접 측정한 값이 아닙니다. |
| `Present Velocity` | 128 | 현재 속도 원시값. `원시값 × 0.229`로 rpm 환산합니다. |
| `Present Position` | 132 | 현재 위치 [pulse]. 다회전 위치 제어에서는 음수나 한 회전을 넘는 값이 가능합니다. |
| `Velocity Trajectory` | 136 | 모터 내부 프로파일이 생성한 목표 속도 궤적. `원시값 × 0.229`로 rpm 환산하며 실제 속도와 구분합니다. |
| `Position Trajectory` | 140 | 모터 내부 프로파일이 생성한 목표 위치 궤적 [pulse]. 최종 목표인 `Goal Position`, 실제 위치인 `Present Position`과 구분합니다. |
| `Present Input Voltage` | 144 | 모터 입력 전압 원시값. `원시값 × 0.1`로 V 환산합니다. 예: 120 → 12.0 V. |
| `Present Temperature` | 146 | 모터 내부 온도 [°C]. 예: 30 → 30°C. |

주소·단위·상태 해석의 근거: [XM430-W210](https://emanual.robotis.com/docs/en/dxl/x/xm430-w210/#control-table),
[XM430-W350](https://emanual.robotis.com/docs/en/dxl/x/xm430-w350/#control-table),
[XL430-W250](https://emanual.robotis.com/docs/en/dxl/x/xl430-w250/#control-table).

### 프로그램이 추가한 환산값

| CSV 열 이름 | 의미 |
| --- | --- |
| `Present Current [mA]` | XM에서 `Present Current × 2.69`로 계산한 전류 [mA]. 원시값 열도 함께 보존합니다. |
| `Present Load [%]` | XL에서 `Present Load × 0.1`로 계산한 부하 추정값 [%]. `Load [kg]`와는 다른 값입니다. |

### Phase 구간 이름

| 이름 또는 접미사 | 의미 |
| --- | --- |
| `UP_…` | 반복 실험에서 기준 위치 → 설정한 목표 위치로 이동. |
| `DOWN_…` | 반복 실험에서 목표 위치 → 기준 위치로 복귀. |
| `…_ACCEL` | 설정한 프로파일의 가속 구간. |
| `…_CONSTANT` | 설정한 프로파일의 등속 구간. |
| `…_DECEL` | 설정한 프로파일의 감속 구간. |
| `…_SETTLE` | 설정한 이동 시간이 지났지만 도착 확인을 기다리는 구간. |
| `TOP_DWELL` | 반복 실험에서 목표 위치에 도착한 후 대기. |
| `BOTTOM_DWELL` | 반복 실험에서 기준 위치에 복귀한 후 대기. |

예: `UP_ACCEL`, `DOWN_DECEL`, `DOWN_SETTLE`.
이동 구간 이름은 PC에서 잰 시간과 설정값으로 분류하며, 실제 속도 곡선을 판별한 결과는 아닙니다.
`UP`과 `DOWN` 역시 코드상의 이름이며 실제 기구의 상승·하강은 장착 방향에 따라 달라질 수 있습니다.

### JSON에 기록되는 정보

| JSON 항목 | 의미 |
| --- | --- |
| `schema_version` | 결과 파일 구조의 버전. 현재 4입니다. |
| `experiment` | 반복 왕복 실험을 뜻하는 `cycle`. |
| `condition` | 부하량을 포함한 실험 조건 이름. |
| `created_at` | 기록 생성 시각과 시간대. |
| `config_file` | 실행할 때 읽은 설정 파일의 경로. |
| `settings` | 당시 전체 설정값의 사본. 나중에 TOML을 수정해도 이 값은 유지됩니다. |
| `model_number` | 실제 연결된 모터의 모델 번호. |
| `firmware_version` | 연결된 모터에서 읽은 펌웨어 버전. |
| `feedback` | 전류/부하 원시값 열 이름, 환산값 열 이름, 환산 계수. |

## 검증 및 협업

```powershell
python -m unittest discover -s tests -v
```

설정 검증, 모델별 매핑, 음수 전류 환산, 모터·조건·부하량별 파일 분리,
반복 동작, 모델 불일치 차단, q 입력 후 왕복 완료와 기준 위치 복귀를 가상 장치로 검증합니다.
실제 U2D2와 모터를 구동한 검증은 별도로 필요합니다.

코드·설정·문서·설계 자료는 Git 관리 대상으로 둡니다.
측정 데이터와 설정 스냅샷, 가상환경, 캐시, 로컬 `docs/`, 설계 자료의 `archive/`는 `.gitignore`로 제외합니다.
측정 데이터는 팀 데이터 저장소나 별도 파일로 공유하세요.
일부 3D 설계 생성·검증 스크립트는 제외된 `archive/` 원본을 참조하므로 실행하려면 해당 자료를 별도로 받아야 합니다.

## 공식 문서

- [XM430-W210 Control Table](https://emanual.robotis.com/docs/en/dxl/x/xm430-w210/#control-table)
- [XM430-W350 Control Table](https://emanual.robotis.com/docs/en/dxl/x/xm430-w350/#control-table)
- [XL430-W250 Control Table](https://emanual.robotis.com/docs/en/dxl/x/xl430-w250/#control-table)
