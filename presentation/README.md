# 발표·검증 자료

이 폴더는 EyesOnU AI Worker의 발표용 시각 자료와 재현용 보조 파일을 모은 곳입니다.

## 구성

- `assets/png`, `assets/svg`: Claude 디자인 기준으로 정리한 오케스트레이션·성능·모델 선택 도표
- `selected`: 발표용으로 선택한 최신 PNG/SVG와 evidence JSON
- `notebooks`: 발표 수치를 다시 읽는 Jupyter 노트북
- `pdf`: 파인튜닝·증류·추론 과정을 설명한 PDF

## 해석 주의

도표의 Recall@5, proxy 속성 점수, 외부 또는 제한된 실험 수치는 서로 같은 지표가 아닙니다. 실제 CCTV 전체의 identity-heldout 일반화 정확도로 바꾸어 말하지 않습니다. 도표의 출처와 범위는 `selected/v4_par_evidence.json`, `ai-worker/docs/PROJECT_AI_ARCHIVE_INDEX.md`, 관련 실험 문서에서 확인합니다.

원본 영상·프레임·개인 식별자·모델 가중치·인증 정보는 이 저장소에 포함하지 않습니다.
