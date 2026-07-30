# Promotion policy

모델을 `APPROVED`로 승격하려면 다음 조건이 모두 필요합니다.

1. 평가 범위가 `sealed_identity_track_heldout`이어야 한다.
2. 독립 identity 라벨, track-heldout 적격성, 사람 검토가 모두 확인되어야 한다.
3. manifest와 evaluation evidence의 상대 경로·SHA-256이 workspace 안에서 다시 검증되어야 한다.
4. attribute Macro-F1, identity Rank-1, Recall@5는 하한을 넘어야 하며 false-match rate는 상한 이하여야 한다.

하나라도 빠지면 결과는 `NOT_APPROVED`다. 이는 모델이 나쁘다는 선언이 아니라, 현재 증거로는 다음 단계에 올릴 수 없다는 뜻이다. 보류 사유는 다음 실험의 데이터·split·검토 조건으로 되돌린다.

