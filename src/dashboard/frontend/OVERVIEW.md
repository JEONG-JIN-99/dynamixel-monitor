# 개요 화면과 데이터 연결

어두운 남색 기반 한국어 화면의 개요 구성과 수신 데이터 연결을 설명한다. 다른 페이지의 구현 상태는 각 페이지 문서를 따른다.

- 왼쪽: 수신된 모델/ID 선택 → 참고 모터 이미지 → 회전/멈춤 → 6개 측정값 → 이상 진단 결과.
- 오른쪽: **데이터 수집 주기 → 최근 60초 → 화면 갱신 0.1초** 정보 바와 전류·속도·위치 그래프.
- 실험 CSV / 가상 데이터 전환은 실제 데이터와 혼동하지 않도록 헤더에 유지한다.
- 모터 선택지는 수신된 metadata/history에서 구성한다. W210과 W350 데이터가 함께 있으면 각각 선택 가능하며, 연결되지 않은 모터의 값을 복제하지 않는다.

## 백엔드와의 경계

`services/motorDataService.ts`는 실제·가상 데이터 모두 WebSocket으로 받는다. `services/telemetryAdapter.ts`가 원시 주소값을 화면용 단위로 변환한다. 백엔드 구조가 바뀌면 이 어댑터에서 `types/motor.ts`의 Message/Sample 형식으로 정규화한다. `stores/motorStore.ts`는 60초 이력, `composables/useOverview.ts`는 모터 선택과 화면 반영을 담당한다. 차트는 props로 선택된 샘플을 받는다.

화면 반영 간격은 100ms이다. 1초 분량 10개 샘플이 한 번에 도착해도 평균내거나 가짜 샘플을 추가하지 않고 원래 측정 시각 그대로 표시한다. **실제 CSV 기록/flush/서버 전송 주기는 이번 프론트엔드 변경에서 바꾸지 않았다.** 데이터가 1초마다 도착하면 실제 값도 그때 바뀐다. 수집 주기는 experiment.sampleIntervalSec, 없으면 system.configuredHz에서 읽고 알 수 없으면 —로 표시한다. mock은 백엔드에서 약 100ms마다 1개 샘플을 생성해 전송한다. [협업 계약](../MOCK_BACKEND.md)을 참고한다.

## 알고리즘 출력 계약 (프론트엔드 준비)

기존 Sample에 선택적으로 다음을 추가할 수 있다. 현재 실제 백엔드는 이를 보내지 않으므로 `판정 대기`가 정상 동작이다.

```json
{
  "diagnosis": {
    "state": "fault",
    "codes": ["overload", "friction"]
  }
}
```

- state: waiting / normal / fault. normal일 때 codes는 빈 배열.
- overvoltage: 과전압, undervoltage: 과소전압, overload: 과부하, undercurrent: 과소전류, friction: 마찰, gear_backlash: 기어 백래시.
- 결과 없음: 판정 대기. 알 수 없는 오류: 미분류 이상. 여러 오류는 함께 표시.
- experiment.condition, sample.status, hwError=0을 알고리즘 정상 판정으로 해석하지 않는다.
- 판정은 해당 샘플의 모델/ID와 시각에 대응한다. 별도 진단 채널을 도입하면 어댑터가 대응되는 샘플에 결합해야 한다. 수집이 멈춘 뒤에는 마지막 측정 기준 결과를 유지한다.
- 가상 데이터의 정상·마찰·과부하 판정은 화면 시연용이며 실제 알고리즘 실행 결과가 아니다.

## 이미지 자산

`src/assets/motor-servo.png`는 built-in Imagegen으로 만든 모터 외형 참고 이미지이다. 모델별 정확한 외관/제품 사진을 보장하지 않는다. 시안 전체를 이미지로 붙인 것이 아니라 모터 그림만 자산으로 사용하고 나머지는 Vue/CSS/ECharts로 구현했다.

생성 프롬프트 (built-in Imagegen):

> Create a clean isolated product illustration asset for a motor monitoring web dashboard. A technically plausible compact Dynamixel XM430-style black rectangular smart servo motor, front-left three-quarter view, silver circular output horn on the front with small screw holes, black machined body with side mounting screw holes. Accurate small industrial actuator proportions, not a cylindrical electric motor. Photorealistic polished engineering product render, crisp edges, soft neutral studio lighting. Center one motor filling 85% of image with generous uniform pure white #FFFFFF surrounding it, very subtle contact shadow. Square composition. Absolutely no labels, no lettering, no logos, no model text, no leader lines, no circles, no annotations, no UI, no other objects. This will be placed directly on a white card in the implemented dashboard.

## 확인

프로젝트 루트에서:

```powershell
npm.cmd --prefix src/dashboard/frontend test
npm.cmd --prefix src/dashboard/frontend run build
npm.cmd --prefix src/dashboard/frontend run test:e2e
```

백엔드 main.py는 frontend/dist를 제공한다. 빌드 후 브라우저에서 Ctrl+F5로 갱신한다. 프론트엔드 개발 서버는 `npm.cmd --prefix src/dashboard/frontend run dev`로 실행한다.
