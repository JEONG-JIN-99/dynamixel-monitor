# 실험용 판

현재 출력 파일:

- [experiment_plate_normal.stl](experiment_plate_normal.stl): 기본 실험판.
- [experiment_plate_friction.stl](experiment_plate_friction.stl): 고정 마찰 가이드 일체형. 상세 치수와 조립 전제는 [마찰판 설명](README_experiment_plate_friction.md).
- [모터 체결부 지름 비교 테스트](tests/experiment_plate_mount_test_D2p5_D2p6_D2p7.stl): Ø2.5/2.6/2.7mm 시험편3개를 하나의 STL에 배치. 각44 × 36 × 20mm, 각구멍4개, 깊이15mm.

## 기본 판 normal

- 외곽 236 × 100mm, 전체 두께 20mm.
- 앞쪽 돌출부 폭 156mm. 양옆 파임 폭 40mm, 깊이 30mm.
- FR12-S102K에서 판 쪽으로 FHS M2.5×14 볼트 4개를 직접 조이는 구성.
- 판 나사 구멍 Ø2.5mm, 깊이 15mm, 바닥 잔여 두께 5mm. 나사산은 모델링하지 않음.
- 구멍 간격 좌우 12mm × 앞뒤 24mm. 중심 좌표 (112,69.5), (124,69.5), (112,93.5), (124,93.5)mm.
- 원점은 뒤쪽 왼쪽 바닥, +Y가 앞쪽. 모터 혼과 릴은 앞쪽을 향함.
- Ø2.4mm 이전 파일에서 구멍 지름만 변경함.

## 관련 자료

- `experiment_plate_normal.blend`: Blender 편집 파일.
- `experiment_plate_normal_preview.png`: 미리보기.
- `experiment_plate_normal_design.json`, `experiment_plate_normal_validation.json`: 치수 및 검증 결과.
- `build_experiment_plate_normal.py`, `verify_experiment_plate_normal.py`: 생성 및 검증 코드.
- `archive/plate_versions_before_normal_D2p5_20260922/`: 기존 S102K 판, 이전 모터 판, 마찰 판, 도면과 테스트/검증 자료 전체 보관.

검증 코드는 보관한 Ø2.4mm 이전 파일과 변경되지 않은 표면을 비교합니다. 실물 체결, 하중 시험 및 슬라이싱은 수행하지 않았습니다.

출력 시 단위 mm, 배율100%, 구멍이 위를 향하도록 놓습니다.
