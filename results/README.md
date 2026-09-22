# 실험 결과

각 CSV 열의 의미·단위와 JSON 항목은 [프로젝트 README의 실험 결과 항목 설명](../README.md#실험-결과-항목-설명)을 참고하세요.

- `raw/<모터 이름>/<실험 조건>/`: 현재 코드가 수집하는 원본 CSV와 실행 설정 JSON.
- `legacy/`: 구조 변경 전에 수집한 기존 CSV 2개. 원본 내용을 유지합니다.

지원 폴더 이름은 `XM430-W210`, `XM430-W350`, `XL430-W250`입니다.
`config/experiment.toml`의 `[motor] name`과 `[condition]`에 따라 폴더가 자동으로 선택됩니다.
저장 경로는 실행 위치와 무관하게 프로젝트 기준입니다.

조건은 `normal`(정상), `overvoltage`(과전압), `undervoltage`(과소전압),
`overload`(과부하), `undercurrent`(과소전류), `friction`(마찰), `gear_backlash`(기어 백래시)입니다.
과부하는 kg 단위의 `load_kg`를 붙여 `overload_0.5kg`, `overload_0.75kg`, `overload_1.5kg`처럼 저장합니다.
다른 조건은 `load_kg = 0`으로 설정하고 `normal`처럼 조건 이름만 사용합니다.
예: `raw/XM430-W210/overload_0.5kg/`. 폴더는 실행 시 자동 생성됩니다.
기존 조건 미분류 파일은 옮기지 않고 그대로 보존합니다.

파일 이름은 `<모터 이름>_<실험 조건>_YYYYMMDD_HHMMSS_ffffff`입니다.
예: `XM430-W210_overload_0.5kg_20260922_143000_123456.csv`.
실행당 CSV 하나와 같은 이름의 JSON을 만듭니다.
JSON에는 당시 설정, 연결 모델 번호, 펌웨어 버전, 전류/부하 환산 정보를 보관합니다.
CSV와 JSON 모두 실험 조건을 기록합니다. CSV의 `Load [kg]`는 사용자가 설정한 과부하량이며
모터가 읽은 `Present Load`와 다른 값입니다. 과부하 이외의 조건에서는 이 열을 비워 둡니다.
오류로 끝난 실행은 일부 데이터 또는 헤더만 포함할 수 있습니다.

XM은 `Present Current` 원시값과 `Present Current [mA]`(×2.69)를 기록합니다.
XL은 `Present Load` 원시값과 `Present Load [%]`(×0.1)를 기록합니다.
나머지 상태값은 Control Table 원시값입니다.
이전 `xl430_log_*.csv`는 OpenCR에서 단위를 변환한 기록이므로 그대로 합치지 않습니다.

CSV와 JSON은 Git 추적에서 제외합니다. 협업자에게는 두 파일을 함께 전달하세요.
이 안내와 `raw/.gitkeep`만 Git으로 공유합니다.
