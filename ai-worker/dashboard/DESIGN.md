# EyesOnU AI Worker 구역 관제 디자인 시스템

## 1. Atmosphere & Identity

기존 EyesOnU 관리자 화면의 밝고 절제된 관제 콘솔을 확장한다. 한 화면에서 구역 확률,
근거 품질, 다음 분석 카메라, 관리자 판단 상태를 빠르게 구분하는 것이 핵심이며, 시그니처는
4개 구역을 실제 배치와 같은 2×2 구조로 보여 주면서 확률의 크기를 좌측 색 띠와 수평 막대로
동시에 표현하는 `ZoneProbabilityCard`다.

## 2. Color

### Palette

| Role | Token | Value | Usage |
|---|---|---|---|
| Surface/page | `--surface-page` | `oklch(0.98 0.005 250)` | 전체 배경 |
| Surface/panel | `--surface-panel` | `oklch(1 0 0)` | 카드와 패널 |
| Surface/subtle | `--surface-subtle` | `oklch(0.965 0.008 240)` | 보조 영역 |
| Surface/selected | `--surface-selected` | `oklch(0.95 0.045 220)` | 선택 구역 |
| Text/primary | `--text-primary` | `oklch(0.2 0.02 250)` | 본문과 제목 |
| Text/secondary | `--text-secondary` | `oklch(0.48 0.02 250)` | 설명과 메타데이터 |
| Text/inverse | `--text-inverse` | `oklch(1 0 0)` | 진한 버튼 위 텍스트 |
| Border/default | `--border-default` | `oklch(0.88 0.01 250)` | 카드와 구분선 |
| Border/strong | `--border-strong` | `oklch(0.78 0.02 245)` | 입력과 포커스 보조 |
| Accent/primary | `--accent-primary` | `oklch(0.55 0.16 220)` | 주요 선택과 확률 막대 |
| Accent/hover | `--accent-hover` | `oklch(0.48 0.15 220)` | 주요 버튼 hover |
| Accent/soft | `--accent-soft` | `oklch(0.93 0.06 220)` | 활성 메뉴와 정보 배경 |
| Status/success | `--status-success` | `oklch(0.53 0.12 155)` | 관리자 확정, 정상 |
| Status/warning | `--status-warning` | `oklch(0.67 0.14 75)` | 검토 필요, 불확실성 |
| Status/error | `--status-error` | `oklch(0.56 0.18 28)` | 제외, 오류 |
| Status/unknown | `--status-unknown` | `oklch(0.58 0.04 255)` | 관할 밖·미확인 |

색은 상태와 상호작용을 구분할 때만 사용한다. 구역 확률의 농도는 accent 계열 안에서만
변화시키며, 높은 확률을 곧 확정으로 오해하게 만드는 성공색은 쓰지 않는다.

## 3. Typography

### Scale

| Level | Size | Weight | Line Height | Usage |
|---|---:|---:|---:|---|
| H1 | 24px | 750 | 1.3 | 페이지 제목 |
| H2 | 17px | 700 | 1.4 | 패널 제목 |
| H3 | 15px | 700 | 1.4 | 카드 제목 |
| Body | 14px | 400 | 1.6 | 기본 본문 |
| Body/sm | 13px | 400 | 1.5 | 표와 보조 설명 |
| Caption | 12px | 600 | 1.4 | 라벨과 상태 |
| Metric | 28px | 760 | 1.1 | 확률과 주요 수치 |

- Primary: `Pretendard, "Noto Sans KR", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`
- Mono: `"SFMono-Regular", Consolas, "Liberation Mono", monospace`
- 한국어 문장은 `word-break: keep-all`을 우선하고, 긴 식별자만 `overflow-wrap: anywhere`를 쓴다.

## 4. Spacing & Layout

기본 단위는 4px다.

| Token | Value | Usage |
|---|---:|---|
| `--space-1` | 4px | 작은 내부 간격 |
| `--space-2` | 8px | 아이콘-라벨, 작은 목록 |
| `--space-3` | 12px | 버튼과 compact 카드 |
| `--space-4` | 16px | 기본 카드 내부 |
| `--space-5` | 20px | 패널 간격 |
| `--space-6` | 24px | 페이지 패딩 |
| `--space-8` | 32px | 큰 구획 간격 |

- 최대 콘텐츠 너비: 1600px
- 데스크톱: 좌측 216px 내비게이션 + 가변 콘텐츠
- 콘텐츠: 12-column CSS grid, 기본 gutter 20px
- 구역 배치: `1 2 / 3 4`의 2×2 고정 의미를 유지한다.
- Breakpoints: mobile 375px, tablet 768px, desktop 1280px
- 1024px 미만에서는 사이드바를 상단 요약 내비게이션으로 축소하고 모든 패널을 한 열로 둔다.

## 5. Components

### AppShell

- **Structure**: `aside + header + main`
- **Variants**: desktop sidebar, compact topbar
- **States**: default, disconnected, loading
- **Accessibility**: landmark와 skip link 제공
- **Motion**: 없음

### StatusBadge

- **Structure**: icon + text
- **Variants**: mock, ready, review, confirmed, rejected, unknown
- **Spacing**: `--space-1`, `--space-2`
- **States**: default와 focus-visible
- **Accessibility**: 색 외 텍스트를 항상 함께 표시
- **Motion**: 없음

### ZoneProbabilityCard

- **Structure**: zone header + metric + probability bar + 2×2 camera cells + evidence summary
- **Variants**: default, focused, next-camera, unavailable
- **Spacing**: `--space-3`, `--space-4`
- **States**: default, hover, focus-visible, selected
- **Accessibility**: button semantics, `aria-pressed`, 확률을 텍스트로 제공
- **Probability semantics**: 카드 4개의 표시값은 관할 내 존재 조건부 확률이며 합계 100%. 원본 6상태 posterior의 `outside`·`unknown`은 안전 로직에만 유지
- **Automatic recommendation**: 조건부 확률이 가장 높은 구역을 기본 선택하되 관리자 판단을 대체하지 않음
- **Motion**: 선택 시 opacity/transform 160ms, reduced-motion에서는 제거

### CameraCell

- **Structure**: camera ID + state + utility
- **Variants**: queued, next, scanned, unavailable
- **Spacing**: `--space-2`
- **States**: default, selected, disabled
- **Accessibility**: 상태를 텍스트와 `aria-label`로 제공
- **Motion**: 없음

### EvidencePanel

- **Structure**: 현재 판단 + 근거 지표 + 경고
- **Variants**: candidate found, review required, broad search
- **States**: loading, populated, empty, error
- **Accessibility**: `aria-live="polite"`로 갱신 상태 통지
- **Motion**: 갱신 시 opacity 160ms

### OperatorDecisionPanel

- **Structure**: 후보 선택 + 확정/검토/제외 버튼 + 연결 상태
- **Variants**: idle, local decision, dispatch ready, unavailable
- **States**: default, hover, active, focus-visible, disabled
- **Accessibility**: 모든 동작을 키보드로 수행, 실제 전송 여부를 즉시 알림
- **Motion**: 버튼 press transform 120ms

### DataTable

- **Structure**: caption + thead + tbody
- **Variants**: candidate, audit
- **States**: populated, empty, loading, error
- **Accessibility**: caption과 column header 제공, 모바일에서는 가로 스크롤
- **Motion**: 없음

## 6. Motion & Interaction

| Type | Duration | Easing | Usage |
|---|---:|---|---|
| Micro | 120ms | ease-out | 버튼 press |
| Standard | 160ms | ease-in-out | 선택 구역 전환 |

- 애니메이션은 `transform`과 `opacity`만 사용한다.
- `prefers-reduced-motion: reduce`에서는 전환을 제거한다.
- 장식용 pulse는 사용하지 않는다. 상태 변화는 텍스트와 badge로 표현한다.

## 7. Depth & Surface

전략은 **borders-only + tonal shift**다. 패널은 `--border-default` 1px과 표면 색 차이로
분리하고, modal/popover가 없는 현재 범위에서는 box-shadow를 사용하지 않는다.

## 8. Accessibility Constraints & Accepted Debt

### Constraints

- WCAG 2.2 AA: 본문 4.5:1, 큰 텍스트와 그래픽 3:1 이상
- 모든 상호작용 요소에 2px focus-visible outline
- 44×44px 터치 목표를 우선하고 최소 38px 미만으로 줄이지 않는다.
- 확률은 색뿐 아니라 숫자, 순위, 상태 텍스트로 중복 표현한다.
- `관할 내 무조건 탐지`를 표시하지 않는다. 사각, 가림, 장애, 관할 이탈 가능성을 별도 상태로 둔다.

### Accepted Debt

| Item | Location | Why accepted | Owner / Exit |
|---|---|---|---|
| 중앙 백엔드 프록시 미연결 | `runtime-config.js` | API 계약과 화면을 먼저 검증하는 현재 작업 범위 | 백엔드 연동 시 mock 모드를 `backend-proxy`로 전환 |
| 실제 16카메라 전이행렬 미반영 | 구역 확률 설명 패널 | 동기화 운영 로그가 아직 없음 | 실카메라 shadow replay 후 모델 artifact 교체 |

