import {
  buildDashboardView,
  candidateStatusLabel,
  formatPercent,
  policyDisplayName,
} from "./domain.js";
import { loadMockScenario, scenarioOptions } from "./mock-data.js";
import { zoneRegionExperiment } from "./experiment-data.js";
import { assertOfflineRuntime, runtimeConfig } from "./runtime-config.js";

assertOfflineRuntime();

const app = document.querySelector("#app");
let selectedScenario = "certain";
let selectedZoneId = null;
let localDecision = "review";

const decisionLabels = Object.freeze({
  confirm: "후보 확정",
  review: "검토 필요",
  reject: "후보 제외",
});

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function statusClass(status) {
  if (status === "candidate_found") return "ready";
  if (status === "review_required" || status === "search_broadly") return "review";
  return "unknown";
}

function cameraCell(camera, nextCameraId) {
  const isNext = camera.cameraId === nextCameraId;
  return `
    <span class="camera-cell${isNext ? " next" : ""}">
      <span class="camera-cell-header">
        <strong>${escapeHtml(camera.cameraId)}</strong>
        <span class="status-badge ${isNext ? "ready" : "unknown"}">${isNext ? "다음" : "대기"}</span>
      </span>
      <small>효용 ${camera.utility.toFixed(4)} · EIG ${camera.expectedInformationGain.toFixed(4)}</small>
    </span>`;
}

function zoneCard(zone, view) {
  const isSelected = selectedZoneId === zone.zoneId;
  const hasCandidate = (zone.summary?.candidateCount ?? 0) > 0;
  const stateLabel = isSelected
    ? `현재 열람 · ${hasCandidate ? "후보 있음" : "후보 없음"}`
    : hasCandidate
      ? "후보 있음"
      : "후보 없음";
  const stateClass = isSelected ? "mock" : hasCandidate ? "review" : "unknown";
  return `
    <button
      class="zone-card"
      type="button"
      data-zone-id="${zone.zoneId}"
      aria-pressed="${isSelected}"
      aria-label="${zone.zoneId}구역, 관할 내 존재를 전제로 한 조건부 모의 확률 ${formatPercent(zone.probability)}, 전체 6상태 원본 확률 ${formatPercent(zone.rawProbability)}"
      style="--probability-opacity: ${Math.max(0.2, zone.probability)}"
    >
      <span class="zone-card-header">
        <span><span class="zone-rank">우선순위 ${zone.rank}</span><h3>${zone.zoneId}구역</h3></span>
        <span class="status-badge ${stateClass}">${stateLabel}</span>
      </span>
      <span class="probability-row">
        <strong class="probability-value">${formatPercent(zone.probability)}</strong>
        <span class="probability-caption">4구역 조건부 posterior</span>
      </span>
      <span class="probability-track" aria-hidden="true">
        <span class="probability-fill" style="--probability-width: ${formatPercent(zone.probability)}"></span>
      </span>
      <span class="camera-grid">
        ${zone.cameras.map((camera) => cameraCell(camera, view.nextCameraId)).join("")}
      </span>
      <span class="zone-meta">
        <span>후보 ${zone.summary?.candidateCount ?? 0}건</span>
        <span>전체 상태 원본 ${formatPercent(zone.rawProbability)}</span>
        <span>Top 후보 ${zone.summary?.topCandidateMatchProbability ? formatPercent(zone.summary.topCandidateMatchProbability) : "없음"}</span>
      </span>
    </button>`;
}

function candidateRows(view) {
  if (view.candidateAssessments.length === 0) {
    return '<tr><td colspan="7">현재 시나리오에는 등록된 후보가 없습니다.</td></tr>';
  }
  return view.candidateAssessments
    .map(
      (candidate) => `
        <tr>
          <td class="mono">${escapeHtml(candidate.eventId)}</td>
          <td>${candidate.zoneId}구역</td>
          <td class="mono">${escapeHtml(candidate.cameraId)}</td>
          <td class="candidate-score">${formatPercent(candidate.matchProbability)}</td>
          <td>${candidate.likelihoodRatio.toFixed(2)}</td>
          <td>${escapeHtml(candidate.priorityBand)}</td>
          <td>${candidate.usedForZoneUpdate ? "반영" : "미반영"}</td>
        </tr>`,
    )
    .join("");
}

function render(view) {
  const nextCamera = view.rankedCameras.find((camera) => camera.cameraId === view.nextCameraId);
  const coverageLabel = view.relativeCoverageSet.map((zoneId) => `${zoneId}구역`).join(" → ");
  const selectedZone = view.zones.find((zone) => zone.zoneId === selectedZoneId);
  const canDecideCandidate = (selectedZone?.summary?.candidateCount ?? 0) > 0;
  const recommendation = view.autoRecommendationAllowed
    ? `${view.mostLikelyZoneId}구역 · ${formatPercent(view.mostLikelyZoneProbability)}`
    : "보류 · 관할 이탈 우세";
  const nextCameraLabel = nextCamera?.cameraId ?? "보류";
  const nextCameraDetail = nextCamera
    ? `효용 ${nextCamera.utility.toFixed(4)} · EIG ${nextCamera.expectedInformationGain.toFixed(4)}`
    : "관할 내 질량 기준 미달 · 자동 카메라 추천 없음";
  const recommendationMethod = view.autoRecommendationAllowed
    ? "자동 · Argmax"
    : "자동 추천 중지";
  app.innerHTML = `
    <div class="app-shell">
      <aside class="sidebar" aria-label="AI Worker 메뉴">
        <div class="brand">
          <span class="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 24 24" role="img"><path d="M2.5 12s3.6-6 9.5-6 9.5 6 9.5 6-3.6 6-9.5 6-9.5-6-9.5-6Zm9.5 3.2a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4Z" fill="currentColor"/></svg>
            <span>EyesOnU</span>
          </span>
          <small>AI Worker 검증 콘솔</small>
        </div>
        <nav class="sidebar-nav" aria-label="주요 메뉴">
          <button class="nav-item active" type="button" aria-current="page">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 13h6V4H4v9Zm0 7h6v-5H4v5Zm10 0h6V11h-6v9Zm0-16v5h6V4h-6Z" fill="currentColor"/></svg>
            <span>구역 확률</span>
          </button>
        </nav>
        <div class="sidebar-footer">연결 사전준비 · 외부 전송 차단</div>
      </aside>
      <div class="app-content">
        <header class="topbar">
          <h1>실종자 탐색 구역 우선순위</h1>
          <div class="topbar-actions">
            <span class="system-time">CASE ${escapeHtml(view.caseId)}</span>
            <span class="status-badge mock">Mock 고정</span>
          </div>
        </header>
        <main id="main-content" class="page">
          <div class="page-heading">
            <div>
              <span class="eyebrow">AI WORKER · REVISION ${view.routingRevision}</span>
              <h2>관할 내 4구역 조건부 확률과 다음 분석 카메라</h2>
              <p>${escapeHtml(view.mockMeta.scenarioDescription)}. 중앙 서버와 Jetson에는 아무 요청도 보내지 않습니다.</p>
            </div>
            <label>
              <span class="screen-reader-status">검증 시나리오</span>
              <select id="scenario-select" class="scenario-select">
                ${scenarioOptions.map((option) => `<option value="${option.value}"${selectedScenario === option.value ? " selected" : ""}>${escapeHtml(option.label)}</option>`).join("")}
              </select>
            </label>
          </div>
          <section class="summary-grid" aria-label="확률 요약">
            <article class="summary-card"><span class="eyebrow">자동 추천 구역</span><strong>${recommendation}</strong><p>관할 내 질량 ${formatPercent(view.jurisdictionProbability)} · 관할 밖 ${formatPercent(view.outsideProbability)} · 정보 부족 ${formatPercent(view.unknownProbability)}</p></article>
            <article class="summary-card"><span class="eyebrow">다음 분석 카메라</span><strong class="mono">${escapeHtml(nextCameraLabel)}</strong><p>${nextCameraDetail}</p></article>
            <article class="summary-card"><span class="eyebrow">추천 방식</span><strong>${recommendationMethod}</strong><p>4개 구역 합계 100%, 관리자가 최종 확인</p></article>
            <article class="summary-card"><span class="eyebrow">불확실성 지수</span><strong>${formatPercent(view.uncertaintyIndex)}</strong><p>자연로그 entropy ÷ ln(6), 낮을수록 판단 집중</p></article>
          </section>
          <div class="dashboard-grid">
            <section class="panel" aria-labelledby="zone-map-title">
              <div class="section-heading">
                <div><h2 id="zone-map-title">4개 구역 확률 지도</h2><p>관할 내 존재 조건부 확률이며 합계는 100%입니다.</p></div>
                <span class="status-badge ${statusClass(view.candidatePoolStatus)}">${candidateStatusLabel(view.candidatePoolStatus)}</span>
              </div>
              <div class="zone-grid">${view.zones.map((zone) => zoneCard(zone, view)).join("")}</div>
            </section>
            <div class="side-stack">
              <section class="panel" aria-labelledby="priority-title">
                <div class="section-heading"><div><h2 id="priority-title">카메라 분석 우선순위</h2><p>${policyDisplayName(view.cameraSelectionPolicy)}</p></div></div>
                <ol class="priority-list">
                  ${view.rankedCameras.slice(0, 6).map((camera, index) => `<li><span class="priority-rank">${index + 1}</span><span><strong class="mono">${escapeHtml(camera.cameraId)}</strong><br><span class="label">${camera.zoneId}구역 · 운영계수 ${camera.operationalFactor.toFixed(2)}</span></span><strong>${camera.utility.toFixed(4)}</strong></li>`).join("")}
                </ol>
                <div class="notice"><strong>관할 내 상대 80% 탐색 집합</strong><span>${coverageLabel}. outside·unknown을 제외한 관할 내 질량의 우선순위 표현이며 탐지 보장률이 아닙니다.</span></div>
              </section>
              <section class="panel" aria-labelledby="decision-title">
                <div class="section-heading"><div><h2 id="decision-title">관리자 로컬 판단</h2><p>화면 검증용 상태만 바뀌며 외부 전송은 차단됩니다.</p></div></div>
                <div class="decision-list" role="group" aria-label="관리자 로컬 판단">
                  <button class="decision-option confirm${localDecision === "confirm" ? " selected" : ""}" data-decision="confirm" type="button" aria-pressed="${localDecision === "confirm"}"${canDecideCandidate ? "" : " disabled"}>후보 확정</button>
                  <button class="decision-option review${localDecision === "review" ? " selected" : ""}" data-decision="review" type="button" aria-pressed="${localDecision === "review"}">검토 필요</button>
                  <button class="decision-option reject${localDecision === "reject" ? " selected" : ""}" data-decision="reject" type="button" aria-pressed="${localDecision === "reject"}"${canDecideCandidate ? "" : " disabled"}>후보 제외</button>
                </div>
                <button class="dispatch-button" type="button" disabled>연결 비활성 · Jetson 전환 불가</button>
                <div class="notice"><strong>사람이 최종 판단</strong><span>모델은 우선순위와 근거를 제공하며 자동 일치는 허용하지 않습니다.</span></div>
              </section>
            </div>
          </div>
          <section class="panel full-width" aria-labelledby="candidate-title">
            <div class="section-heading"><div><h2 id="candidate-title">후보 근거</h2><p>후보 확률과 구역 존재확률은 서로 다른 값입니다.</p></div><span class="status-badge mock">모의 증거</span></div>
            <p class="table-scroll-hint">좁은 화면에서는 표를 좌우로 스크롤해 전체 근거를 확인할 수 있습니다.</p>
            <div class="table-scroll" tabindex="0" role="region" aria-label="AI Worker 후보 근거 표, 좌우 스크롤 가능">
              <table class="data-table">
                <caption>AI Worker 후보 근거 목록</caption>
                <thead><tr><th>이벤트</th><th>구역</th><th>카메라</th><th>동일인 확률</th><th>Likelihood ratio</th><th>우선 등급</th><th>구역 갱신</th></tr></thead>
                <tbody>${candidateRows(view)}</tbody>
              </table>
            </div>
          </section>
          <section class="panel full-width" aria-labelledby="experiment-title">
            <div class="section-heading"><div><h2 id="experiment-title">4구역 자동 선택 검증</h2><p>선택용 검증으로 조합을 고른 뒤, 봉인 데이터는 선택된 조합에 한 번만 사용했습니다.</p></div><span class="status-badge review">합성 proxy 통과 · 운영 미승격</span></div>
            <div class="experiment-grid">
              <div><span class="eyebrow">실험 선택 조합</span><strong>Expected Bayes + Logistic</strong><p>${zoneRegionExperiment.routeCount}개 탐색 방식 × ${zoneRegionExperiment.modelCount}개 모델 비교 · 런타임 미통합</p></div>
              <div><span class="eyebrow">Sealed Top-1 · 합성 proxy</span><strong>${formatPercent(zoneRegionExperiment.sealedTest.accuracy, 2)}</strong><p>${zoneRegionExperiment.sealedTest.correct.toLocaleString("ko-KR")} / ${zoneRegionExperiment.sealedTest.total.toLocaleString("ko-KR")}건 정답</p></div>
              <div><span class="eyebrow">Wilson 95% 하한</span><strong>${formatPercent(zoneRegionExperiment.sealedTest.wilson95Lower, 2)}</strong><p>목표 ${formatPercent(zoneRegionExperiment.sealedTest.gate, 0)}보다 ${formatPercent(zoneRegionExperiment.sealedTest.wilson95Lower - zoneRegionExperiment.sealedTest.gate, 2)}p 높음</p></div>
              <div><span class="eyebrow">증거 범위</span><strong>${zoneRegionExperiment.rowCount.toLocaleString("ko-KR")} proxy 행</strong><p>실제 CCTV 승격 전 독립 track-heldout 재검증 필요</p></div>
            </div>
          </section>
          <p class="method-note">표시값은 관할 내 존재를 전제로 4개 구역만 재정규화한 deterministic mock입니다. 91.88%는 합성 topology proxy의 봉인 결과이며 실제 CCTV 일반화 수치가 아닙니다. outside·unknown 상태는 안전 판단을 위해 내부 응답에 유지되고, 운영 승격은 동기화된 이동·관측 로그의 track-heldout 결과로 결정합니다.</p>
          <div class="screen-reader-status" aria-live="polite">현재 ${escapeHtml(view.mockMeta.scenarioLabel)}, 선택 구역 ${selectedZoneId === null ? "없음" : `${selectedZoneId}구역`}, 로컬 판단 ${decisionLabels[localDecision]}</div>
        </main>
      </div>
    </div>`;
  bindInteractions();
}

function bindInteractions() {
  document.querySelector("#scenario-select")?.addEventListener("change", async (event) => {
    selectedScenario = event.target.value;
    const response = await loadMockScenario(selectedScenario);
    const view = buildDashboardView(response);
    selectedZoneId = view.mostLikelyZoneId;
    localDecision = "review";
    render(view);
    document.querySelector("#scenario-select")?.focus();
  });
  document.querySelectorAll("[data-zone-id]").forEach((button) => {
    button.addEventListener("click", async () => {
      selectedZoneId = Number(button.dataset.zoneId);
      localDecision = "review";
      render(buildDashboardView(await loadMockScenario(selectedScenario)));
      document.querySelector(`[data-zone-id="${selectedZoneId}"]`)?.focus();
    });
  });
  document.querySelectorAll("[data-decision]").forEach((button) => {
    button.addEventListener("click", async () => {
      localDecision = button.dataset.decision;
      render(buildDashboardView(await loadMockScenario(selectedScenario)));
      document.querySelector(`[data-decision="${localDecision}"]`)?.focus();
    });
  });
}

loadMockScenario(selectedScenario)
  .then((response) => {
    const view = buildDashboardView(response);
    selectedZoneId = view.mostLikelyZoneId;
    render(view);
  })
  .catch((error) => {
    app.innerHTML = `<main class="showcase-page"><div class="notice"><strong>화면 초기화 실패</strong><span>${escapeHtml(error.message)}</span></div></main>`;
  });
