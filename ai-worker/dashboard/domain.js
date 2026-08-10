const ZONE_COUNT = 4;
const POSTERIOR_STATE_COUNT = 6;
const SUM_TOLERANCE = 1e-6;
const CANDIDATE_POOL_STATUSES = new Set([
  "candidate_found",
  "review_required",
  "search_broadly",
]);
const PRIORITY_BANDS = new Set(["high_priority", "review", "low_priority"]);
const CAMERA_SELECTION_POLICY = "posterior_weighted_coverage_with_eig_tiebreak";
export const MOCK_AUTOMATIC_RECOMMENDATION_POLICY = Object.freeze({
  policyId: "dashboard_mock_jurisdiction_mass_v1",
  minimumJurisdictionMass: 0.5,
  scope: "dashboard_mock_safety_heuristic",
  operationallyApproved: false,
});

function requireFiniteNumber(value, name, minimum = -Infinity, maximum = Infinity) {
  if (!Number.isFinite(value) || value < minimum || value > maximum) {
    throw new Error(`${name} 값이 허용 범위를 벗어났습니다.`);
  }
}

function requireString(value, name) {
  if (typeof value !== "string" || value.length === 0) {
    throw new Error(`${name} 문자열이 필요합니다.`);
  }
}

export function formatPercent(value, digits = 1) {
  return `${(value * 100).toFixed(digits)}%`;
}

export function normalizedUncertainty(entropy) {
  return Math.min(1, Math.max(0, entropy / Math.log(POSTERIOR_STATE_COUNT)));
}

export function buildRelativeCoverageSet(zonePosterior, target = 0.8) {
  if (!(target > 0 && target <= 1)) {
    throw new Error("탐색 집합 목표는 0보다 크고 1 이하여야 합니다.");
  }
  const totalZoneMass = zonePosterior.reduce((sum, item) => sum + item.probability, 0);
  if (totalZoneMass <= 0) {
    return [];
  }
  const ranked = [...zonePosterior].sort(
    (left, right) => right.probability - left.probability || left.zoneId - right.zoneId,
  );
  const selected = [];
  let cumulative = 0;
  for (const item of ranked) {
    selected.push(item.zoneId);
    cumulative += item.probability / totalZoneMass;
    if (cumulative >= target) {
      break;
    }
  }
  return selected;
}

export function buildConditionalZonePosterior(zonePosterior) {
  const totalZoneMass = zonePosterior.reduce((sum, item) => sum + item.probability, 0);
  if (totalZoneMass <= SUM_TOLERANCE) {
    const uniformProbability = 1 / zonePosterior.length;
    return zonePosterior.map((item) => ({
      ...item,
      rawProbability: item.probability,
      probability: uniformProbability,
    }));
  }
  return zonePosterior.map((item) => ({
    ...item,
    rawProbability: item.probability,
    probability: item.probability / totalZoneMass,
  }));
}

export function validateProbabilityResponse(response) {
  if (!response || typeof response !== "object") {
    throw new Error("확률 응답 객체가 필요합니다.");
  }
  if (response.schemaVersion !== "eyesonu-zone-search-v1") {
    throw new Error("지원하지 않는 확률 응답 버전입니다.");
  }
  if (!Number.isSafeInteger(response.caseId) || response.caseId < 1) {
    throw new Error("caseId는 1 이상의 안전한 정수여야 합니다.");
  }
  if (!Number.isInteger(response.routingRevision) || response.routingRevision < 1) {
    throw new Error("routingRevision은 1 이상의 정수여야 합니다.");
  }
  if (!CANDIDATE_POOL_STATUSES.has(response.candidatePoolStatus)) {
    throw new Error("candidatePoolStatus가 허용 목록에 없습니다.");
  }
  if (!Array.isArray(response.zonePosterior) || response.zonePosterior.length !== ZONE_COUNT) {
    throw new Error("zonePosterior는 4개 구역을 모두 포함해야 합니다.");
  }
  const zoneIds = new Set();
  for (const item of response.zonePosterior) {
    if (!Number.isInteger(item.zoneId) || item.zoneId < 1 || item.zoneId > ZONE_COUNT) {
      throw new Error("zoneId는 1부터 4까지의 정수여야 합니다.");
    }
    if (zoneIds.has(item.zoneId)) {
      throw new Error("zonePosterior에 중복 zoneId가 있습니다.");
    }
    zoneIds.add(item.zoneId);
    requireFiniteNumber(item.probability, "구역 확률", 0, 1);
  }
  requireFiniteNumber(response.outsideProbability, "outsideProbability", 0, 1);
  requireFiniteNumber(response.unknownProbability, "unknownProbability", 0, 1);
  const total =
    response.zonePosterior.reduce((sum, item) => sum + item.probability, 0) +
    response.outsideProbability +
    response.unknownProbability;
  if (Math.abs(total - 1) > SUM_TOLERANCE) {
    throw new Error(`posterior 합이 1이 아닙니다: ${total}`);
  }
  if (
    !Array.isArray(response.zoneCandidateSummaries) ||
    response.zoneCandidateSummaries.length !== ZONE_COUNT
  ) {
    throw new Error("zoneCandidateSummaries는 4개 구역을 모두 포함해야 합니다.");
  }
  const summaryZoneIds = new Set();
  for (const summary of response.zoneCandidateSummaries) {
    if (
      !Number.isInteger(summary.zoneId) ||
      summary.zoneId < 1 ||
      summary.zoneId > ZONE_COUNT ||
      summaryZoneIds.has(summary.zoneId)
    ) {
      throw new Error("zoneCandidateSummaries의 zoneId가 잘못됐습니다.");
    }
    summaryZoneIds.add(summary.zoneId);
    if (!Number.isInteger(summary.candidateCount) || summary.candidateCount < 0) {
      throw new Error("candidateCount는 0 이상의 정수여야 합니다.");
    }
    requireFiniteNumber(summary.zonePresenceProbability, "zonePresenceProbability", 0, 1);
    if (summary.topCandidateEventId !== null) {
      requireString(summary.topCandidateEventId, "topCandidateEventId");
    }
    if (summary.topCandidateMatchProbability !== null) {
      requireFiniteNumber(summary.topCandidateMatchProbability, "topCandidateMatchProbability", 0, 1);
    }
  }
  if (!Array.isArray(response.candidateAssessments)) {
    throw new Error("candidateAssessments 배열이 필요합니다.");
  }
  for (const candidate of response.candidateAssessments) {
    requireString(candidate.eventId, "candidate.eventId");
    requireString(candidate.trackId, "candidate.trackId");
    requireString(candidate.cameraId, "candidate.cameraId");
    requireString(candidate.observationGroupId, "candidate.observationGroupId");
    requireString(candidate.observedAt, "candidate.observedAt");
    if (!Number.isInteger(candidate.zoneId) || candidate.zoneId < 1 || candidate.zoneId > ZONE_COUNT) {
      throw new Error("candidate.zoneId가 잘못됐습니다.");
    }
    requireFiniteNumber(candidate.matchProbability, "candidate.matchProbability", 0, 1);
    requireFiniteNumber(candidate.likelihoodRatio, "candidate.likelihoodRatio", Number.MIN_VALUE);
    if (!PRIORITY_BANDS.has(candidate.priorityBand) || typeof candidate.usedForZoneUpdate !== "boolean") {
      throw new Error("후보 우선등급 또는 반영 상태가 잘못됐습니다.");
    }
  }
  if (!Number.isInteger(response.mostLikelyZoneId) || !zoneIds.has(response.mostLikelyZoneId)) {
    throw new Error("mostLikelyZoneId가 4개 구역에 속하지 않습니다.");
  }
  requireFiniteNumber(response.mostLikelyZoneProbability, "mostLikelyZoneProbability", 0, 1);
  requireFiniteNumber(
    response.posteriorEntropy,
    "posteriorEntropy",
    0,
    Math.log(POSTERIOR_STATE_COUNT) + SUM_TOLERANCE,
  );
  const mostLikely = response.zonePosterior.find(
    (item) => item.zoneId === response.mostLikelyZoneId,
  );
  if (
    !mostLikely ||
    Math.abs(mostLikely.probability - response.mostLikelyZoneProbability) > SUM_TOLERANCE
  ) {
    throw new Error("최우선 구역 확률이 zonePosterior와 일치하지 않습니다.");
  }
  if (!response.operatorReviewRequired || response.autoMatchAllowed) {
    throw new Error("관리자 검토 필수 및 자동 일치 금지 불변식이 깨졌습니다.");
  }
  if (!Array.isArray(response.rankedCameras) || response.rankedCameras.length === 0) {
    throw new Error("카메라 우선순위가 비어 있습니다.");
  }
  const cameraIds = new Set();
  for (const camera of response.rankedCameras) {
    requireString(camera.cameraId, "cameraId");
    if (cameraIds.has(camera.cameraId)) {
      throw new Error("rankedCameras에 중복 cameraId가 있습니다.");
    }
    cameraIds.add(camera.cameraId);
    if (
      !Number.isInteger(camera.zoneId) ||
      camera.zoneId < 1 ||
      camera.zoneId > ZONE_COUNT ||
      !Number.isInteger(camera.position) ||
      camera.position < 1 ||
      camera.position > 4
    ) {
      throw new Error("카메라 구역 또는 위치가 잘못됐습니다.");
    }
    if (camera.cameraId !== `${camera.zoneId}-${camera.position}`) {
      throw new Error("cameraId가 구역-위치 계약과 일치하지 않습니다.");
    }
    requireFiniteNumber(camera.zoneProbability, "camera.zoneProbability", 0, 1);
    requireFiniteNumber(camera.expectedInformationGain, "camera.expectedInformationGain", 0);
    requireFiniteNumber(camera.operationalFactor, "camera.operationalFactor", 0, 1);
    requireFiniteNumber(camera.utility, "camera.utility", 0);
  }
  if (response.cameraSelectionPolicy !== CAMERA_SELECTION_POLICY) {
    throw new Error("승인되지 않은 cameraSelectionPolicy입니다.");
  }
  if (response.nextCameraId !== response.rankedCameras[0].cameraId) {
    throw new Error("nextCameraId가 카메라 우선순위 1위와 다릅니다.");
  }
  return response;
}

export function buildDashboardView(response) {
  validateProbabilityResponse(response);
  const conditionalZonePosterior = buildConditionalZonePosterior(response.zonePosterior);
  const jurisdictionProbability = response.zonePosterior.reduce(
    (sum, item) => sum + item.probability,
    0,
  );
  const autoRecommendationAllowed =
    jurisdictionProbability >=
    MOCK_AUTOMATIC_RECOMMENDATION_POLICY.minimumJurisdictionMass;
  const jurisdictionStatus =
    response.outsideProbability >= Math.max(jurisdictionProbability, response.unknownProbability)
      ? "outside_dominant"
      : response.unknownProbability >= Math.max(jurisdictionProbability, response.outsideProbability)
        ? "unknown_dominant"
        : autoRecommendationAllowed
          ? "in_jurisdiction"
          : "low_jurisdiction_mass";
  const cameraByZone = Map.groupBy(response.rankedCameras, (camera) => camera.zoneId);
  const summaryByZone = new Map(
    response.zoneCandidateSummaries.map((summary) => [summary.zoneId, summary]),
  );
  const rankedZones = [...conditionalZonePosterior].sort(
    (left, right) => right.probability - left.probability || left.zoneId - right.zoneId,
  );
  const conditionalZonePosteriorFallback = jurisdictionProbability <= SUM_TOLERANCE ? "uniform" : null;
  const rankByZone = new Map(
    conditionalZonePosteriorFallback === null
      ? rankedZones.map((item, index) => [item.zoneId, index + 1])
      : [],
  );
  return {
    ...response,
    rawMostLikelyZoneProbability: response.mostLikelyZoneProbability,
    jurisdictionProbability,
    jurisdictionStatus,
    conditionalZonePosteriorFallback,
    autoRecommendationAllowed,
    rankedCameras: autoRecommendationAllowed ? response.rankedCameras : [],
    mostLikelyZoneId: autoRecommendationAllowed ? response.mostLikelyZoneId : null,
    mostLikelyZoneProbability: autoRecommendationAllowed
      ? conditionalZonePosterior.find((item) => item.zoneId === response.mostLikelyZoneId)
          .probability
      : null,
    nextCameraId: autoRecommendationAllowed ? response.nextCameraId : null,
    uncertaintyIndex: normalizedUncertainty(response.posteriorEntropy),
    relativeCoverageSet: buildRelativeCoverageSet(conditionalZonePosterior),
    zones: conditionalZonePosterior
      .toSorted((left, right) => left.zoneId - right.zoneId)
      .map((item) => ({
        ...item,
        rank: rankByZone.get(item.zoneId) ?? null,
        summary: summaryByZone.get(item.zoneId),
        cameras: (cameraByZone.get(item.zoneId) ?? []).toSorted(
          (left, right) => left.position - right.position,
        ),
      })),
  };
}

export function policyDisplayName(policy) {
  const names = {
    posterior_weighted_coverage_with_eig_tiebreak: "posterior × 운영계수 + EIG 동률 해소",
  };
  return names[policy] ?? policy;
}

export function candidateStatusLabel(status) {
  const labels = {
    candidate_found: "후보 발견",
    review_required: "검토 필요",
    search_broadly: "광역 탐색",
  };
  return labels[status] ?? status;
}

