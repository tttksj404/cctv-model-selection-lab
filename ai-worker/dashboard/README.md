# AI Worker 구역 확률 검증 대시보드

AI Worker가 계산한 관할 내 4개 구역 조건부 확률, 카메라 효용과 다음 분석
카메라를 운영자 관점에서 검증하기 위한 독립 화면이다. 현재 단계에서는 중앙 백엔드,
Jetson, 실제 AI Worker API와 연결하지 않는다.

이 4구역 화면은 사용자 시나리오를 검증하는 사전 실험이며, 저장소의 공식 2구역 MVP
요구사항이나 운영 API 계약을 변경하지 않는다. 공식 요구사항·API가 4구역으로 승인되기
전에는 실험 결과를 런타임에 승격하지 않는다.

4구역 Top-1 모델 비교와 85% 게이트 결과는
[`docs/ZONE_REGION_MODEL_EXPERIMENT_20260802.md`](../docs/ZONE_REGION_MODEL_EXPERIMENT_20260802.md)에 기록한다.

## 현재 안전 경계

- `runtime-config.js`는 `mock`/`disabled`/네트워크 금지로 고정되어 있다.
- 관리자 판단 버튼은 브라우저 로컬 상태만 바꾸고 전송 버튼은 항상 비활성이다.
- 브라우저에 `X-Internal-API-Key` 또는 다른 비밀값을 넣지 않는다.
- `80% 탐색 집합`은 관할 내 posterior 질량의 우선순위 집합이며 탐지 성공 보장이 아니다.
- 모델은 자동 일치를 허용하지 않고 관리자 검토를 필수로 유지한다.

## 실행과 검증

```powershell
npm.cmd install
npm.cmd test
npm.cmd run build
npm.cmd run qa:browser
npm.cmd run dev -- --port 4173
```

`qa:browser`는 빌드 결과를 임시 preview 포트에 올리고 실제 Chrome으로 375/768/1280px
화면을 조작한다. 시나리오·구역·로컬 판단 전환, 전송 버튼 비활성, 브라우저 오류 및
외부 호스트 요청 0건을 함께 검사한 뒤 preview 서버를 종료한다.

시나리오 선택기로 예상 위치 확실/불확실, 현재 관할 가능성, 관할 이탈 가능성을 바꿔
4개 구역 표시 확률 합 100%, 자동 추천 구역, 다음 카메라, 불확실성, 후보 근거가 함께
변하는지 확인한다. `outside`/`unknown`은 요약 카드에 원본 확률로 함께 표시하고, 관할 내
질량이 50% 미만이면 구역 자동 추천을 보류한다. 이 기준은
`dashboard_mock_jurisdiction_mass_v1` mock 안전 휴리스틱이며 운영 승인을 받지 않았다.
구역 카드의 4개 값은 관할 내 존재를
전제로 한 조건부 확률이며 원본 6상태 확률도 카드 하단에 병기한다.

## 나중에 연결할 때

브라우저가 AI Worker 내부 endpoint를 직접 호출하지 않는다. 중앙 백엔드가 AI Worker 결과를
저장·권한검사·감사한 뒤 동일 출처의 관리자용 프록시로 반환해야 한다. 현재 중앙
백엔드의 `/api/v1/admin/cases/{caseId}` 네임스페이스, 양의 정수 `caseId`,
`EYESONU_SESSION` 세션 쿠키, `ApiResponse<T>` 래퍼에 맞춘 초안 계약은
`contracts/zone-dashboard-proxy.openapi.yaml`에 있다. 중앙 백엔드는 AI Worker 결과를
공통 응답의 `data`에 담아 반환한다. 실제 연결 변경은 다음 조건을 모두
충족하는 별도 작업으로 수행한다.

1. 중앙 백엔드 API 경로와 인증 방식 확정
2. `eyesonu-zone-search-v1` 응답 스키마 contract test 통과
3. 확률 합 1, 4개 고유 zone, `nextCameraId == rankedCameras[0]` 검증
4. `operatorReviewRequired=true`, `autoMatchAllowed=false` 유지
5. 관리자 결정 idempotency와 감사 로그 검증
6. `requestId` nonce와 사건별 최신 revision을 DB에서 원자적으로 소비하는 replay 방어

실제 연결 전까지 mock adapter를 네트워크 adapter로 바꾸지 않는다.
