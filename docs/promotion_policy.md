# Promotion gate 정책

이 gate는 모델 선택 흐름 전체의 마지막 단계입니다. 후보가 `APPROVED`가 되려면 다음을 모두 만족해야 합니다.

1. 측정 범위가 `sealed_identity_track_heldout`이어야 합니다.
2. 독립 identity label, track-heldout 적격성, 사람 검토가 모두 있어야 합니다.
3. manifest와 evaluation evidence가 workspace 내부 경로와 SHA-256으로 다시 확인되어야 합니다.
4. attribute Macro-F1, identity Rank-1, Recall@5는 하한 이상이고 false-match rate는 상한 이하여야 합니다.

조건 하나라도 빠지면 `NOT_APPROVED`입니다. 이는 모델을 폐기한다는 뜻이 아니라, 현재 증거만으로는 자동 적용을 정당화할 수 없다는 뜻입니다. 보류 사유는 다음 manifest 설계, candidate 비교, 사람 검토 규칙으로 되돌아갑니다.
