# 모델 선택 아키텍처

## 문제를 역할로 나눴다

생성형 모델 하나가 탐지·속성·동일인·설명을 모두 대신하도록 설계하지 않았습니다. 출력 공간과 검증 기준이 다른 작업을 분리하고, 각 결과가 충분한 경우에만 다음 단계로 전달되도록 했습니다.

| 단계 | 담당 | 입력과 출력 | 차단 조건 |
| --- | --- | --- | --- |
| 탐지·추적 | detector / tracker | 영상 또는 프레임에서 person track과 품질 정보 생성 | track·시간 정보가 없으면 비교 제외 |
| 임베디드 후보 | `student_CLIP_hard` | 빠른 속성 후보와 confidence | 서버 증거를 대체하지 않음 |
| 서버 속성 | `SOLIDER Swin-B + PAR` | 구조화된 multi-label 속성 확률 | calibration 또는 track evidence 부족 시 review |
| ReID | SOLIDER·TransReID 계열 | Top-K 동일인 후보와 margin | strict 기준 미달이면 자동 match 금지 |
| 생성형 검토 | Qwen 계열 | 모델 충돌·저신뢰도 이유와 구조화된 보조 설명 | 직접 점수 합산 금지 |
| 결정 엔진 | deterministic fusion | match, review, reject | 충돌·증거 부족이면 fail-closed |

## 하네스, 오케스트레이션, 루프

하네스는 manifest, notebook, 결과 JSON, artifact hash, gate report를 묶어 같은 실행이 같은 조건인지 확인하는 장치입니다. 오케스트레이션은 임베디드 후보, 서버 PAR, ReID, 생성형 검토를 순서와 권한에 맞춰 호출하고, 생성형 결과를 최종 판정 권한에서 분리하는 구조입니다.

현재 runtime은 `provisional`이고 production 승인 상태가 아닙니다. ReID는 runtime에서 retrieval-only로 제한하며, 생성형 모델은 primary identity classifier·자동 fallback·auto-match 필수 조건이 아닙니다. 이 제한은 현재 수치가 아니라 역할과 권한의 경계를 보존하기 위한 정책입니다.

루프는 `spec → baseline → single change → measure → gate → keep or revert`입니다. proxy 속성 지표가 좋아도 identity·track-heldout·사람 검토가 없으면 승격하지 않습니다. strict ReID 재비교에서 이전 overlap 결과보다 낮은 수치가 나왔을 때도, 더 높은 overlap 수치를 채택하지 않고 strict 결과를 기준으로 자동 매칭을 차단했습니다.

## 데이터와 AI 보안

모든 측정은 manifest의 group·camera·track·시간 분리와 provenance를 전제로 합니다. 현재 프로젝트 identity 정답은 10개 사람 검토 stable track 안에서만 유효하고, 교차 카메라 identity 정답은 없습니다. 동일 identity가 train·test를 넘거나, 인접 frame이 분리된 것처럼 보이거나, teacher label의 이용 조건·근거가 비어 있으면 결과를 보류합니다. 생성형 모델은 저신뢰도 또는 충돌 설명에만 사용하며, 비공개 영상·개인 식별자·내부 경로를 공개 스냅샷에 넣지 않습니다.
