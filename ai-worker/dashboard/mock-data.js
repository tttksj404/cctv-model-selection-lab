const ZONE_CAMERAS = Object.freeze(
  [1, 2, 3, 4].flatMap((zoneId) =>
    [1, 2, 3, 4].map((position) => ({
      cameraId: `${zoneId}-${position}`,
      zoneId,
      position,
    })),
  ),
);

const operationalFactor = Object.freeze({
  "1-1": 0.93,
  "1-2": 0.91,
  "1-3": 0.86,
  "1-4": 0.74,
  "2-1": 0.95,
  "2-2": 0.89,
  "2-3": 0.84,
  "2-4": 0.9,
  "3-1": 0.92,
  "3-2": 0.88,
  "3-3": 0.81,
  "3-4": 0.86,
  "4-1": 0.94,
  "4-2": 0.9,
  "4-3": 0.83,
  "4-4": 0.87,
});

const scenarioDefinitions = Object.freeze({
  certain: {
    label: "예상 위치 확실 · 1구역 후보 발견",
    description: "강한 후보 증거가 1구역 posterior를 높인 상태",
    probabilities: [0.62, 0.06, 0.05, 0.05],
    outside: 0.09,
    unknown: 0.13,
    status: "candidate_found",
    candidateZone: 1,
    candidateProbability: 0.87,
  },
  uncertain: {
    label: "예상 위치 불확실 · 광역 탐색",
    description: "증거가 약해 네 구역 대표 카메라를 순차 분석하는 상태",
    probabilities: [0.19, 0.17, 0.16, 0.14],
    outside: 0.11,
    unknown: 0.23,
    status: "search_broadly",
    candidateZone: null,
    candidateProbability: null,
  },
  current: {
    label: "현재 관할 가능성 높음 · 4구역",
    description: "최근 영상 증거와 이동 prior가 4구역을 함께 지지하는 상태",
    probabilities: [0.08, 0.05, 0.07, 0.52],
    outside: 0.12,
    unknown: 0.16,
    status: "review_required",
    candidateZone: 4,
    candidateProbability: 0.68,
  },
  outside: {
    label: "관할 이탈 가능성 높음",
    description: "경계 카메라의 마지막 관측 뒤 outside posterior가 증가한 상태",
    probabilities: [0.08, 0.07, 0.06, 0.05],
    outside: 0.55,
    unknown: 0.19,
    status: "review_required",
    candidateZone: 4,
    candidateProbability: 0.43,
  },
});

function entropy(probabilities) {
  return -probabilities.reduce(
    (total, probability) => total + (probability > 0 ? probability * Math.log(probability) : 0),
    0,
  );
}

function cameraInformationGain(zoneProbability, position) {
  const balance = 1 - Math.abs(0.5 - zoneProbability) * 1.4;
  const overlapPenalty = (position - 1) * 0.008;
  return Math.max(0.01, Number((0.08 + balance * 0.095 - overlapPenalty).toFixed(4)));
}

function buildResponse(key, definition) {
  const zonePosterior = definition.probabilities.map((probability, index) => ({
    zoneId: index + 1,
    probability,
  }));
  const rankedCameras = ZONE_CAMERAS.map((camera) => {
    const zoneProbability = definition.probabilities[camera.zoneId - 1];
    const expectedInformationGain = cameraInformationGain(zoneProbability, camera.position);
    const factor = operationalFactor[camera.cameraId];
    return {
      ...camera,
      zoneProbability,
      expectedInformationGain,
      operationalFactor: factor,
      utility: Number((zoneProbability * factor).toFixed(4)),
    };
  }).sort(
    (left, right) =>
      right.utility - left.utility ||
      right.expectedInformationGain - left.expectedInformationGain ||
      left.cameraId.localeCompare(right.cameraId),
  );
  const candidateAssessments = definition.candidateZone
    ? [
        {
          eventId: `mock-${key}-event-01`,
          trackId: `mock-${key}-track-01`,
          zoneId: definition.candidateZone,
          cameraId: `${definition.candidateZone}-1`,
          observationGroupId: `mock-${key}-segment-01`,
          observedAt: "2026-08-01T05:42:00Z",
          matchProbability: definition.candidateProbability,
          likelihoodRatio: Number((definition.candidateProbability * 69.23).toFixed(2)),
          priorityBand: definition.candidateProbability >= 0.8 ? "high_priority" : "review",
          signalCount: 3,
          usedForZoneUpdate: true,
        },
      ]
    : [];
  return Object.freeze({
    schemaVersion: "eyesonu-zone-search-v1",
    caseId: 17,
    routingRevision: 7,
    candidateAssessments,
    candidatePoolStatus: definition.status,
    zonePosterior,
    zoneCandidateSummaries: zonePosterior.map(({ zoneId, probability }) => {
      const candidate = candidateAssessments.find((item) => item.zoneId === zoneId);
      return {
        zoneId,
        candidateCount: candidate ? 1 : 0,
        topCandidateEventId: candidate?.eventId ?? null,
        topCandidateMatchProbability: candidate?.matchProbability ?? null,
        zonePresenceProbability: probability,
      };
    }),
    mostLikelyZoneId: zonePosterior.toSorted((a, b) => b.probability - a.probability)[0].zoneId,
    mostLikelyZoneProbability: Math.max(...definition.probabilities),
    posteriorEntropy: Number(
      entropy([...definition.probabilities, definition.outside, definition.unknown]).toFixed(4),
    ),
    outsideProbability: definition.outside,
    unknownProbability: definition.unknown,
    rankedCameras,
    nextCameraId: rankedCameras[0].cameraId,
    cameraSelectionPolicy: "posterior_weighted_coverage_with_eig_tiebreak",
    operatorReviewRequired: true,
    autoMatchAllowed: false,
    mockMeta: {
      scenarioKey: key,
      scenarioLabel: definition.label,
      scenarioDescription: definition.description,
      generatedAt: "2026-08-01T06:00:00Z",
    },
  });
}

export const mockScenarios = Object.freeze(
  Object.fromEntries(
    Object.entries(scenarioDefinitions).map(([key, definition]) => [
      key,
      buildResponse(key, definition),
    ]),
  ),
);

export const scenarioOptions = Object.freeze(
  Object.entries(scenarioDefinitions).map(([value, definition]) => ({
    value,
    label: definition.label,
  })),
);

export async function loadMockScenario(key) {
  const response = mockScenarios[key];
  if (!response) {
    throw new Error(`알 수 없는 mock 시나리오: ${key}`);
  }
  return structuredClone(response);
}
