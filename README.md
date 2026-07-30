# CCTV Model Evaluation Harness

진행 중인 CCTV 사람 속성·식별 후보 모델 실험에서, 모델 점수 자체보다 **승격 가능한 증거가 갖춰졌는지**를 판단하기 위해 만든 공개 포트폴리오판입니다.

이 저장소는 모델·영상·원본 라벨을 배포하지 않습니다. 대신 다음 흐름을 독립적으로 재현합니다.

```text
run manifest + evaluation evidence
        ↓
provenance / identity-label / track-heldout 확인
        ↓
metric·운영 임계값 검증
        ↓
APPROVED 또는 NOT_APPROVED + 사유
```

## 왜 만들었나

현재 실험에서는 CLIP, SOLIDER, ReID, Qwen3-VL 등 후보의 역할을 나누고 같은 조건에서 비교합니다. 다만 proxy 속성 점수가 좋아도 실제 CCTV identity·track-heldout 라벨과 독립 검수가 없으면 모델을 승격하지 않습니다. 이 저장소는 그 보류 기준을 코드·합성 예제·테스트로 보여 줍니다.

공개판에 포함된 예제는 합성 데이터입니다. 원본 CCTV 영상, 사람 식별자, 모델 가중치, 팀 서비스 코드, API 키, 원격 서버 주소는 포함하지 않습니다.

## 빠른 실행

Python 3.11 이상에서 실행합니다.

```powershell
python -m pip install -e .
python -m unittest discover -s tests -v
python -m cctv_eval_harness.gate --input examples/proxy_result.json --config configs/promotion_gate.json --workspace .
```

두 번째 명령은 의도적으로 `NOT_APPROVED`를 반환합니다. 예제는 proxy 벤치마크이며 독립 identity 라벨·track-heldout 검증·검증 가능한 산출물 참조가 없기 때문입니다. 종료 코드 `2`는 실행 실패가 아니라 승격 보류를 뜻합니다.

## 공개한 핵심

- `src/cctv_eval_harness/gate.py`: workspace 밖의 산출물 경로를 거부하고 SHA-256을 다시 확인하는 fail-closed 승격 게이트
- `configs/promotion_gate.json`: identity Rank-1, Recall@5, false-match rate, review rate의 명시적 기준
- `examples/proxy_result.json`: proxy 결과를 production 성과로 오해하지 않도록 `NOT_APPROVED`로 닫는 예제
- `notebooks/evaluation_protocol.ipynb`: 실험 질문·기준선·비교 지표·보류 조건을 기록할 Jupyter 템플릿
- `docs/session_evidence.md`: 공개 가능한 실험 사실과 표현 경계

## 이력서용 설명

> CCTV 후보 모델의 manifest·결과 JSON·근거 파일을 함께 검증하는 Python 평가 하네스를 설계했습니다. proxy 점수가 높아도 identity·track-heldout·독립 라벨·provenance가 부족하면 `NOT_APPROVED`로 보류하고, 실패 사유를 다음 실험 조건으로 환류했습니다.

이 문장은 성능 수치나 production 배포를 주장하지 않습니다. 현재 단계의 핵심은 모델 도입 전에 검증 가능한 승격 조건을 만드는 것입니다.

## 범위와 한계

- 이 프로젝트는 실제 CCTV 배포 서비스가 아닙니다.
- 예제의 승인 경로는 단위 테스트용 합성 산출물로만 검증합니다.
- 실제 승격에는 권한 있는 데이터, 사람 검수, identity·track 분리, 라이선스 검토가 추가로 필요합니다.

자세한 근거와 공개 범위는 [docs/session_evidence.md](docs/session_evidence.md), 게이트 규칙은 [docs/promotion_policy.md](docs/promotion_policy.md)를 참고하세요.
