# 노트북 카메라 실시간 실종자 후보 탐색

## 실행 결과

이 프로그램은 노트북 카메라에서 사람을 실시간 검출하고, 입력한 인상착의와
가장 비슷한 사람을 화면에 표시한다.

- YOLO11x: 사람 검출 및 ByteTrack 추적
- CLIP ViT-L/14: 상·하의 색상, 안경, 머리, 상의 형태, 전체 문장 유사도
- SOLIDER-ReID Swin Base: 기준 사진 동일인 검증 또는 최초 안정 후보 재식별
- 시간 누적 점수: 한 프레임 오판을 줄이기 위해 3회 이상 관측 후 후보 확정

## 최초 설치

프로젝트 루트에서 다음 명령을 한 번 실행한다.

```powershell
uv sync --extra realtime
```

모델 가중치는 용량과 라이선스 때문에 Git에 포함하지 않는다. 다음 경로에 검증된
파일을 준비한다.

```text
models/yolo11x.pt
models/solider_reid/swin_base_msmt17.pth
```

SOLIDER 실행 코드는 공식 저장소의 고정 커밋만 허용한다.

```powershell
git clone https://github.com/tinyvision/SOLIDER-REID.git `
  external/SOLIDER-REID-runtime-8c08e1c
git -C external/SOLIDER-REID-runtime-8c08e1c checkout `
  8c08e1c3255e8e1e51e006bf189e52cc57b009ed
```

가중치 SHA-256은 `configs/realtime_model_manifest.json`과 일치해야 한다.
다른 파일이면 모델을 GPU에 올리기 전에 실행이 중단된다.

## 인상착의만으로 실행

명령줄에서 프로필을 생략하면 별도 입력 창이 먼저 열린다. 입력 후 `확인`을
누르면 해당 프로필로 모델을 로드하고 카메라 탐색을 시작한다.

```powershell
uv run --extra realtime eyesonu-realtime
```

프로필을 명령에 직접 넣어 바로 시작할 수도 있다.

```powershell
uv run --extra realtime eyesonu-realtime --appearance "회색 반팔 검은색 바지 안경 넘긴머리 남자"
```

이 모드에서는 CLIP이 3회 이상 일관되게 찾은 첫 후보를 SOLIDER 기준 인물로
자동 등록한다. 이후 자세 변화나 잠깐의 가림으로 ByteTrack ID가 바뀌어도
SOLIDER 동일인 유사도를 함께 사용한다.

## 기준 사진까지 사용

동일인 확인이 중요한 실제 운용에서는 실종자 기준 전신 사진을 함께 지정한다.

```powershell
uv run --extra realtime eyesonu-realtime `
  --appearance "회색 반팔 검은색 바지 안경 넘긴머리 남자" `
  --reference-image "C:\data\missing-person.jpg"
```

기준 사진이 있으면 첫 프레임부터 CLIP 인상착의와 SOLIDER 동일인 점수를 모두
통과해야 후보가 된다. 텍스트만으로는 사람의 신원을 증명할 수 없으므로 이 모드가
실제 실종자 확인에 더 적합하다.

## 조작

- `Q` 또는 `ESC`: 종료
- 카메라 창의 `X`: 종료
- `S`: 현재 대시보드 저장
- 기본 저장 위치: `artifacts/realtime_demo/latest.jpg`

## 바탕화면에서 다시 실행

`EYES_ON_U_실시간_실종자_탐색` 바탕화면 바로가기를 더블클릭하면
프로필 입력창부터 다시 시작한다. 카메라 창을 `Q`, `ESC`, 또는 `X`로
종료한 뒤에도 같은 바로가기로 언제든 다시 실행할 수 있다.

바로가기가 없는 환경에서는 프로젝트 루트의
`launch_eyesonu_realtime.cmd`를 더블클릭해도 동일하게 실행된다.

카메라가 0번이 아니면 `--camera-index 1`처럼 바꾼다. 다른 가중치를 시험할 때는
`--yolo-weights`, `--solider-checkpoint`, `--solider-root`만 바꾸면 되며, 가중치는
`configs/realtime_model_manifest.json`에 SHA-256을 등록해야 실행된다.

## 화면 점수 해석

화면의 유사도 점수는 확률이 아니라 후보 순위를 위한 휴리스틱 점수다.

- `인상착의 유사도 높음`: 지정 속성과 필수 게이트를 통과한 안정 후보
- `인상착의 재검토`: 일부 속성이 가렸거나 SOLIDER 동일인 점수가 부족한 상태
- `인상착의 유사도 낮음`: 현재 관측이 신고 내용과 충분히 다름

여러 사람이 비슷한 점수이면 자동 확정하지 않고 모두 재검토로 낮춘다.

