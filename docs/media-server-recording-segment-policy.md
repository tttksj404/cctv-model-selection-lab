# 녹화 세그먼트 정책

## 결정

AI Worker로 보내는 녹화본의 기본 단위는 **카메라별 30초의 닫힌 fMP4 세그먼트**로 한다.
중앙 서버는 세그먼트 길이를 강제하지 않고, 미디어 서버가 전달한 실제 `startTime`과
`endTime`을 기준으로 등록한다. MediaMTX의 `recordSegmentDuration`은 최소 길이이므로
키프레임 정렬 때문에 실제 길이가 30초보다 조금 길어질 수 있다. 따라서 백엔드에서
정확히 30초만 허용하는 검증은 추가하지 않는다.

현재 백엔드의 `POST /api/v1/device/cameras/{cameraCode}/recordings`도 시작·종료 시각과
MP4 object key만 검증한다. 즉, RP5의 MediaMTX 설정이 세그먼트 길이의 단일 진실 공급원이다.
설정이 없으면 MediaMTX의 기본 `recordSegmentDuration`은 1시간이므로 반드시 명시한다.

## 권장 MediaMTX 설정

```yaml
pathDefaults:
  record: yes
  recordFormat: fmp4
  # 장애가 나도 마지막 1초 정도만 복구 지점에서 잃도록 한다.
  recordPartDuration: 1s
  # AI Worker의 기본 입력 단위. 실제 종료 시각은 키프레임에 맞춰 약간 달라질 수 있다.
  recordSegmentDuration: 30s
  recordPath: /var/lib/mediamtx/recordings/%path/%Y/%m/%d/%H/%M/%S-%f
  # 완전히 닫힌 파일만 업로드·등록한다.
  runOnRecordSegmentComplete: /opt/eyesonu/bin/publish-recording-segment.sh
```

`publish-recording-segment.sh`는 MediaMTX가 제공하는 `MTX_PATH`, `MTX_SEGMENT_PATH`,
`MTX_SEGMENT_DURATION`을 사용한다. 파일 생성 이벤트가 아니라 완료 이벤트에서 실행해야
부분 파일을 AI Worker가 내려받는 경쟁 상태가 생기지 않는다.

## 업로드·등록 순서

1. 스크립트가 닫힌 세그먼트를 MinIO의 `recordings/{cameraCode}/.../*.mp4`에 업로드한다.
2. 업로드 성공과 객체 크기 확인 뒤, 파일명에 포함한 시작 시각과 실제 세그먼트 길이로
   `startTime`, `endTime`을 계산한다.
3. 같은 object key에 대해 안정적으로 만든 UUID를 `Idempotency-Key`로 사용해 중앙 서버의
   녹화본 등록 API를 호출한다.
4. 중앙 서버가 등록한 녹화본만 분석 작업의 대상으로 삼는다. 재시도는 같은
   `Idempotency-Key`로 수행한다.

AI Worker는 한 작업에서 하나의 세그먼트만 내려받되, `searchFromMs`와 `searchToMs`로
해당 세그먼트 내부의 유효 탐색 구간만 추론한다.

## 30초를 선택한 이유

| 선택 | 장점 | 단점 | 판정 |
| --- | --- | --- | --- |
| 30초 | 후보가 늦어도 약 30초 후에는 닫힌 파일로 등록되어 재시도 단위와 최초 후보 지연이 작다. | 1분보다 객체·등록 호출 수가 2배다. | 기본값 |
| 1분 | 객체 수와 등록 호출이 적다. | 후보 등록과 실패 재처리 단위가 최대 1분으로 늘어난다. | 보조 선택지 |
| 1시간 기본값 | 설정이 없어도 동작한다. | 실종자 후보의 최초 등록과 재처리가 너무 늦고, 한 파일 실패 비용이 크다. | 사용 금지 |

모델은 노트북에 상주하므로 1분 세그먼트가 모델 기동비를 특별히 절약하지 않는다. 반대로
30초 세그먼트는 구역 우선순위 갱신과 관리자의 후보 확인을 더 빠르게 만든다.

## 경계 처리

세그먼트 경계에서 인물이 잘리지 않게 다음 규칙을 적용한다.

- 저장 파일 자체를 중복 저장하지 않는다.
- 후보가 세그먼트의 처음 또는 마지막 2초에 있으면, 인접 세그먼트를 우선 분석 작업으로
  추가한다.
- 인접 세그먼트에서 나온 후보는 카메라, 시간 간격, 임베딩 유사도로 묶어 관리자 화면에서
  중복 후보가 되지 않게 처리한다. 로컬 tracker ID만으로는 세그먼트 간 동일인을 보장할 수
  없다.

## 검증 기준

- MediaMTX에서 30초 설정으로 연속 세그먼트 3개를 만들고, 각 등록 메타데이터의
  `endTime > startTime` 및 object key를 확인한다.
- 첫·마지막 2초에 사람이 등장하는 영상을 넣어 인접 세그먼트 작업이 생성되는지 확인한다.
- 동일 파일 업로드 훅을 재시도해도 같은 `Idempotency-Key`가 중복 녹화본을 만들지 않는지
  확인한다.
- 1분 세그먼트도 계약상 처리 가능한지 회귀 테스트하되, 운영 기본값은 30초로 유지한다.

## 근거

- [MediaMTX 녹화 문서](https://mediamtx.org/docs/features/record): 기본 `recordSegmentDuration`은
  1시간이며, `recordPartDuration`은 장애 시 복구 지점(RPO)을 결정한다.
- [MediaMTX 훅 문서](https://mediamtx.org/docs/features/hooks):
  `runOnRecordSegmentComplete`에서 완료된 세그먼트 경로와 실제 길이를 제공한다.
