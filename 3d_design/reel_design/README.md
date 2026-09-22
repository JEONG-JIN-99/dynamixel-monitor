# 최종 Reel 디자인

- [Reel_w210.stl](Reel_w210.stl): W210용, 허리 지름 61.2mm.
- [Reel_w350.stl](Reel_w350.stl): W350용, 허리 지름 83.6mm.

현재 출력 대상은 위 두 STL입니다. 2026-09-22 수정한 Ø2.5mm 체결 구멍 버전이며, 폴더 정리와 이름 변경으로 형상은 바뀌지 않았습니다.

## 공통 치수

- 양옆 체결 구멍 4개: Ø2.5mm, 깊이 14.5mm, 바닥 기준 중심높이 5mm, 같은 면 구멍 간격 22mm.
- 중앙 바닥 홈: Ø5mm, 깊이 3mm.
- 체결부: 33.6 × 47.6 × 12.7mm. 전체 릴 높이 48.7mm.
- 허리 시작/중앙/끝: 바닥 기준 22.7 / 25.2 / 27.7mm.

## 관련 파일

- `Reel_w210.blend`, `Reel_w350.blend`: Blender 편집 파일.
- `Reel_w210_underside.png`, `Reel_w350_underside.png`: 밑면 미리보기.
- `build_reels.py`, `reel_geometry_helpers.py`: 생성 코드.
- `verify_reels.py`, `design.json`, `verification.json`: 설계 정보 및 검증 코드/결과.
- `archive/`: 이전 릴과 테스트용 체결부. 현재 출력 대상이 아닙니다. 보관본 이름은 이력을 위해 유지했습니다.

생성 코드와 검증 코드는 `archive/reel_cleanup_20260922_D2p5/reel_design/` 안의 원본/직전 최종 파일을 참조합니다. 재생성을 위해 보관 폴더를 유지합니다. 기존 build.log는 파일명 변경 전 생성 이력입니다.

STL을 별도 재가져와 폐쇄 단일 입체, 면 방향, 구멍 치수 및 통로, 기존 몸통 보존을 검사했습니다. 실물 체결과 하중 시험은 아직 수행하지 않았습니다.
