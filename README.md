# CCTV Model Selection Lab

진행 중인 CCTV 모델 선택 실험을 공개 가능한 형태로 정리한 포트폴리오 저장소입니다. 이 저장소의 핵심은 단일 모델의 점수를 보여 주는 것이 아니라, 각 모델을 맞는 역할에 배치하고 검증 조건을 통과한 결과만 다음 단계로 넘기는 의사결정 과정입니다.

```mermaid
flowchart LR
    A["검토된 manifest"] --> B["역할별 후보 분리"]
    B --> C["동일 조건 후보 비교"]
    C --> D["strict ReID Top-K 검색"]
    D --> E["속성·시간·공간 증거 결합"]
    E --> F{"충돌 또는 증거 부족"}
    F -->|"예"| G["review / reject"]
    F -->|"아니오"| H["promotion gate"]
    H --> I["APPROVED 또는 NOT_APPROVED"]
```

## 무엇을 선택했는가

| 역할 | 현재 후보·상태 | 선택 원칙 |
| --- | --- | --- |
| 임베디드 1차 후보 | `student_CLIP_hard`, proxy 우선 | 낮은 복잡도의 1차 후보만 만들고 최종 판정은 하지 않습니다. |
| 서버 속성 인식 | `SOLIDER Swin-B + PAR`, 구현 후보 | 사람 속성의 구조화된 multi-label 출력을 담당합니다. |
| 동일인 검색 | SOLIDER ReID, Top-K 후보 검색만 허용 | strict 교차 카메라·시퀀스 비교에서 자동 매칭 기준을 통과하지 못하면 차단합니다. |
| 생성형 모델 | Qwen 계열, 충돌·저신뢰도 검토 보조 | 속성 분류기나 자동 동일인 판정기를 대체하지 않습니다. |

현재 strict ReID 재비교에서 가장 높은 후보는 SOLIDER-ReID Swin-B Top-3 mean입니다. Rank-1 `0.4737`, Recall@5 `0.7789`, identity-MRR `0.6074`였으며, 자동 동일인 매칭 기준인 Rank-1 `0.85`와 Recall@5 `0.95`를 통과하지 못했습니다. 따라서 후보 검색에는 쓰되 자동 매칭은 `BLOCKED`로 유지합니다.

현재 runtime은 `provisional`이며 `productionApproved = false`입니다. retrieval-only 제한은 runtime에서 강제하고, 생성형 모델은 자동 fallback이나 primary identity classifier가 아닙니다. 교차 카메라 identity 정답도 아직 없으므로, 현재 사람 검토 track의 identity는 원래 source track 안에서만 유효하게 취급합니다.

## 비교와 루프의 경계

- 현재 속성 proxy는 PA-100K local 100-image subset의 6개 필드별 top-1 평균 `0.7267`입니다. 이 값은 CCTV identity·track-heldout 결과나 외부 benchmark의 mA·InsF1과 동등하지 않습니다.
- 이전 45개 person crop·33개 그룹 비교의 CLIP ViT-L/14 `0.414`, Qwen3-VL-2B `0.393`은 historical proxy로 보존합니다. 현재 선택 기준으로 섞지 않으며, 역할이 다른 ReID 점수와 합산하거나 순위를 섞지 않습니다.
- `invalid_runtime`과 `pending` 후보는 0점으로 환산하지 않고 비교 대상에서 제외합니다. 실패 원인을 실행 환경·출력 계약·미측정으로 남겨 다음 실험의 입력으로 사용합니다.
- manifest에는 `identityGroupId`, `cameraId`, `trackId`, `conditionGroupId`, 시간 인접성을 분리하는 규칙과 사람 검토·teacher provenance를 요구합니다. 누락·누수·미승인 teacher가 있으면 결과를 보류합니다.
- 최종 gate는 독립 identity label, track-heldout, 사람 검토, artifact hash와 품질 기준을 모두 요구합니다. 하나라도 부족하면 `NOT_APPROVED`가 정상 결과입니다.

## 저장소 구성

- [configs/model_selection_snapshot.json](configs/model_selection_snapshot.json): 역할, 후보 상태, 측정 범위, strict ReID 결정과 promotion 상태를 한 파일에 고정한 공개용 스냅샷
- [docs/model-selection-architecture.md](docs/model-selection-architecture.md): 모델 역할과 fail-closed 오케스트레이션 구조
- [docs/experiment-decision-log.md](docs/experiment-decision-log.md): 비교 결과를 어떤 범위에서 해석했는지와 다음 실험 루프
- [src/cctv_eval_harness/gate.py](src/cctv_eval_harness/gate.py): 전체 흐름의 마지막 promotion gate 컴포넌트
- [notebooks/model_selection_overview.ipynb](notebooks/model_selection_overview.ipynb): 스냅샷을 다시 읽어 의사결정 경계를 확인하는 실행 가능한 요약
- [notebooks/evaluation_protocol.ipynb](notebooks/evaluation_protocol.ipynb): artifact·heldout·provenance gate 프로토콜

## 실행

Python 3.11 이상과 `uv`에서 테스트·gate를 실행합니다. Notebook 실행에는 Jupyter 환경이 필요합니다.

```powershell
uv run python -m unittest discover -s tests -v
uv run python -m cctv_eval_harness.gate --input examples/proxy_result.json --config configs/promotion_gate.json --workspace .
python -m nbconvert --to notebook --execute --inplace notebooks/model_selection_overview.ipynb --ExecutePreprocessor.timeout=60
```

두 번째 명령은 의도적으로 `NOT_APPROVED`와 종료 코드 `2`를 반환합니다. proxy 속성 결과를 실제 CCTV identity·track-heldout 결과처럼 승격하지 않는지 확인하기 위한 fail-closed 예제입니다.

## 공개 범위

실제 CCTV 영상·프레임·개인 식별자·모델 가중치·내부 서버 경로·인증 정보는 포함하지 않습니다. 이 저장소는 원본 데이터를 재배포하지 않고, 어떤 증거가 있어야 모델 선택 또는 승격이 가능한지 재현 가능한 의사결정 구조만 공개합니다.


## AI Worker 전체 자료 아카이브

현재 프로젝트에서 진행한 CCTV 모델 비교, 파인튜닝·지식 증류, SOLIDER/CLIP/Qwen 역할 분리, RabbitMQ 작업 흐름, 구역 검색 정책, 발표용 도표와 쉬운 설명서를 한 곳에 모았습니다.

- [AI Worker 자료실 색인](ai-worker/docs/PROJECT_AI_ARCHIVE_INDEX.md)
- [AI Worker 코드와 문서](ai-worker/)
- [발표용 도표·노트북·PDF](presentation/)
- [기존 fail-closed 평가 하네스](src/cctv_eval_harness/)

공개 저장소에는 원본 CCTV, 개인 식별 라벨, 모델 가중치, API key, private GPU/Jupyter 주소를 넣지 않았습니다. 발표용 Recall@5와 proxy 결과는 실제 프로젝트 전체 identity 일반화 정확도와 구분해서 읽어야 하며, 자동 동일인 확정은 독립 held-out 증거가 있을 때만 허용합니다.
