import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  buildDashboardView,
  buildConditionalZonePosterior,
  buildRelativeCoverageSet,
  MOCK_AUTOMATIC_RECOMMENDATION_POLICY,
  normalizedUncertainty,
  validateProbabilityResponse,
} from "../domain.js";
import { mockScenarios } from "../mock-data.js";
import { policyExperiment, zoneRegionExperiment } from "../experiment-data.js";

test("all mock scenarios preserve probability and human-review invariants", () => {
  for (const response of Object.values(mockScenarios)) {
    assert.equal(validateProbabilityResponse(response), response);
    assert.equal(response.operatorReviewRequired, true);
    assert.equal(response.autoMatchAllowed, false);
  }
});

test("relative coverage uses only in-jurisdiction zone mass", () => {
  const selected = buildRelativeCoverageSet([
    { zoneId: 1, probability: 0.62 },
    { zoneId: 2, probability: 0.06 },
    { zoneId: 3, probability: 0.05 },
    { zoneId: 4, probability: 0.05 },
  ]);
  assert.deepEqual(selected, [1, 2]);
});

test("conditional dashboard probabilities sum to one across four zones", () => {
  const conditional = buildConditionalZonePosterior([
    { zoneId: 1, probability: 0.08 },
    { zoneId: 2, probability: 0.16 },
    { zoneId: 3, probability: 0.04 },
    { zoneId: 4, probability: 0.12 },
  ]);

  assert.deepEqual(
    conditional.map((item) => Number(item.probability.toFixed(8))),
    [0.2, 0.4, 0.1, 0.3],
  );
  assert.deepEqual(
    conditional.map((item) => item.rawProbability),
    [0.08, 0.16, 0.04, 0.12],
  );
  assert.ok(
    Math.abs(conditional.reduce((sum, item) => sum + item.probability, 0) - 1) < 1e-12,
  );
});

test("zero in-jurisdiction mass uses a uniform conditional fallback", () => {
  const conditional = buildConditionalZonePosterior([
    { zoneId: 1, probability: 0 },
    { zoneId: 2, probability: 0 },
    { zoneId: 3, probability: 0 },
    { zoneId: 4, probability: 0 },
  ]);

  assert.deepEqual(
    conditional.map((item) => item.probability),
    [0.25, 0.25, 0.25, 0.25],
  );
  assert.deepEqual(
    conditional.map((item) => item.rawProbability),
    [0, 0, 0, 0],
  );
});

test("outside-dominant zero mass remains safe for the dashboard view", () => {
  const response = structuredClone(mockScenarios.outside);
  response.zonePosterior.forEach((item) => {
    item.probability = 0;
  });
  response.zoneCandidateSummaries.forEach((summary) => {
    summary.zonePresenceProbability = 0;
  });
  response.mostLikelyZoneProbability = 0;
  response.outsideProbability = 1;
  response.unknownProbability = 0;
  response.posteriorEntropy = 0;

  const view = buildDashboardView(response);

  assert.equal(view.jurisdictionProbability, 0);
  assert.equal(view.jurisdictionStatus, "outside_dominant");
  assert.equal(view.conditionalZonePosteriorFallback, "uniform");
  assert.equal(view.autoRecommendationAllowed, false);
  assert.equal(view.mostLikelyZoneId, null);
  assert.equal(view.nextCameraId, null);
  assert.deepEqual(view.rankedCameras, []);
  assert.deepEqual(view.zones.map((zone) => zone.rank), [null, null, null, null]);
  assert.deepEqual(view.relativeCoverageSet, [1, 2, 3, 4]);
  assert.deepEqual(
    view.zones.map((zone) => zone.probability),
    [0.25, 0.25, 0.25, 0.25],
  );

  const unknownDominantResponse = structuredClone(response);
  unknownDominantResponse.outsideProbability = 0;
  unknownDominantResponse.unknownProbability = 1;
  const unknownDominantView = buildDashboardView(unknownDominantResponse);

  assert.equal(unknownDominantView.jurisdictionStatus, "unknown_dominant");
  assert.equal(unknownDominantView.conditionalZonePosteriorFallback, "uniform");
  assert.deepEqual(unknownDominantView.zones.map((zone) => zone.rank), [null, null, null, null]);
});

test("dashboard view places the ranked first camera in nextCameraId", () => {
  const view = buildDashboardView(mockScenarios.current);
  assert.equal(view.nextCameraId, view.rankedCameras[0].cameraId);
  assert.equal(view.zones.length, 4);
  assert.equal(view.mostLikelyZoneId, 4);
  assert.ok(Math.abs(view.zones.reduce((sum, item) => sum + item.probability, 0) - 1) < 1e-12);
  assert.equal(
    view.mostLikelyZoneProbability,
    view.zones.find((item) => item.zoneId === view.mostLikelyZoneId).probability,
  );
  assert.equal(
    view.rawMostLikelyZoneProbability,
    mockScenarios.current.mostLikelyZoneProbability,
  );
  assert.equal(view.jurisdictionProbability, 0.72);
  assert.equal(view.autoRecommendationAllowed, true);
});

test("outside-dominant scenarios block automatic zone recommendation", () => {
  const view = buildDashboardView(mockScenarios.outside);

  assert.ok(Math.abs(view.jurisdictionProbability - 0.26) < 1e-12);
  assert.equal(view.outsideProbability, 0.55);
  assert.equal(view.unknownProbability, 0.19);
  assert.equal(view.autoRecommendationAllowed, false);
  assert.equal(view.mostLikelyZoneId, null);
  assert.equal(view.mostLikelyZoneProbability, null);
  assert.equal(view.nextCameraId, null);
});

test("uncertainty index is bounded to zero and one", () => {
  assert.equal(normalizedUncertainty(-1), 0);
  assert.equal(normalizedUncertainty(Math.log(6)), 1);
  assert.equal(normalizedUncertainty(999), 1);
});

test("invalid probability sum is rejected", () => {
  const invalid = structuredClone(mockScenarios.certain);
  invalid.outsideProbability = 0.5;
  assert.throws(() => validateProbabilityResponse(invalid), /posterior 합/);
});

test("future proxy text fields are rejected before HTML rendering", () => {
  const invalidStatus = structuredClone(mockScenarios.certain);
  invalidStatus.candidatePoolStatus = '<img src=x onerror="alert(1)">';
  assert.throws(() => validateProbabilityResponse(invalidStatus), /허용 목록/);

  const invalidPolicy = structuredClone(mockScenarios.certain);
  invalidPolicy.cameraSelectionPolicy = '<svg onload="alert(1)">';
  assert.throws(() => validateProbabilityResponse(invalidPolicy), /승인되지 않은/);
});

test("hybrid policy is not promoted when its paired interval includes zero", () => {
  assert.equal(policyExperiment.rawSelectionWinner, "hybrid_eig_0_25");
  assert.equal(policyExperiment.pairedResolvedDelta95.includesZero, true);
  assert.equal(policyExperiment.promotionAccepted, false);
  assert.equal(policyExperiment.runtimePolicy, "deployed_runtime");
});

test("dashboard experiment summary matches the sealed v3 replay artifact", () => {
  const artifact = JSON.parse(
    readFileSync(
      new URL(
        "../../experiments/results/zone_policy_risk_replay_large_20260801.json",
        import.meta.url,
      ),
      "utf8",
    ),
  );
  const replay = artifact.topologyReplayEvidence;
  const promotion = artifact.promotionDecision;
  const sealed = replay.sealedTestCohort;

  assert.equal(policyExperiment.artifact, "experiments/results/zone_policy_risk_replay_large_20260801.json");
  assert.equal(policyExperiment.schemaVersion, artifact.schemaVersion);
  assert.equal(policyExperiment.seed, artifact.seed);
  assert.equal(policyExperiment.episodesPerCellPerCohort, artifact.episodesPerCellPerCohort);
  assert.equal(policyExperiment.policyCount, Object.keys(sealed.aggregateByPolicy).length);
  assert.equal(policyExperiment.pairedRecordCount, artifact.pairedOutcomeEvidence.recordCount);
  assert.equal(policyExperiment.pairedEvidenceSha256, artifact.pairedOutcomeEvidence.sha256);
  assert.equal(policyExperiment.rawSelectionWinner, artifact.selectedPolicy);
  assert.equal(policyExperiment.runtimePolicyId, artifact.selectedRuntimePolicy);
  assert.deepEqual(policyExperiment.deployed, sealed.aggregateByPolicy.deployed_runtime);
  assert.deepEqual(policyExperiment.selectedHybrid, sealed.aggregateByPolicy[artifact.selectedPolicy]);
  const interval = sealed.pairedComparisonsAgainstDeployed[artifact.selectedPolicy]
    .resolvedWithinBudgetRate;
  assert.deepEqual(policyExperiment.pairedResolvedDelta95, {
    delta: interval.delta,
    lower: interval.delta95Lower,
    upper: interval.delta95Upper,
    includesZero: interval.includesZero,
  });
  assert.equal(
    policyExperiment.promotionAccepted,
    promotion.proxyMaterialImprovementOverDeployedConfirmed,
  );
  assert.equal(
    policyExperiment.selectionPairedIntervalPassed,
    promotion.selectionPairedIntervalPassed,
  );
  assert.equal(
    policyExperiment.sealedTestPairedIntervalPassed,
    promotion.sealedTestPairedIntervalPassed,
  );
  assert.equal(policyExperiment.projectCctvEvidence, replay.projectCctvEvidence);
});

test("four-zone model summary matches the sealed GPU comparison artifact", () => {
  const artifactUrl = new URL(
    "../../experiments/results/zone_region_model_comparison_20260802.json",
    import.meta.url,
  );
  const artifactBytes = readFileSync(artifactUrl);
  const artifact = JSON.parse(artifactBytes.toString("utf8"));
  const manifest = JSON.parse(
    readFileSync(
      new URL(
        "../../experiments/results/evidence/zone_region_dataset_manifest_20260802.json",
        import.meta.url,
      ),
      "utf8",
    ),
  );
  const selected = artifact.selected;

  assert.equal(
    zoneRegionExperiment.artifactSha256,
    createHash("sha256").update(artifactBytes).digest("hex"),
  );
  assert.equal(zoneRegionExperiment.selectionDatasetSha256, artifact.selectionDatasetSha256);
  assert.equal(zoneRegionExperiment.schemaVersion, artifact.schemaVersion);
  assert.equal(zoneRegionExperiment.sealedDatasetSha256, artifact.sealedDatasetSha256);
  assert.equal(zoneRegionExperiment.selectionCommitmentSha256, artifact.selectionCommitmentSha256);
  assert.equal(zoneRegionExperiment.featureSchemaSha256, artifact.featureSchemaSha256);
  assert.equal(zoneRegionExperiment.modelArtifactSha256, selected.sealedMetrics.artifactSha256);
  assert.equal(artifact.selectionDatasetSha256, manifest.datasets.selection.sha256);
  assert.equal(artifact.sealedDatasetSha256, manifest.datasets.sealed_test.sha256);
  assert.equal(zoneRegionExperiment.selectedRoute, selected.route);
  assert.equal(zoneRegionExperiment.selectedModel, selected.model);
  assert.equal(zoneRegionExperiment.activationStatus, artifact.activationStatus);
  assert.deepEqual(zoneRegionExperiment.scope, artifact.scope);
  assert.deepEqual(
    zoneRegionExperiment.automaticRecommendationPolicy,
    artifact.automaticRecommendationPolicy,
  );
  assert.deepEqual(
    zoneRegionExperiment.automaticRecommendationPolicy,
    MOCK_AUTOMATIC_RECOMMENDATION_POLICY,
  );
  assert.equal(zoneRegionExperiment.promotionAccepted, artifact.promotionDecision.accepted);
  assert.deepEqual(
    zoneRegionExperiment.promotionReasonCodes,
    artifact.promotionDecision.reasonCodes,
  );
  assert.deepEqual(zoneRegionExperiment.selectionValidation, {
    total: selected.selectionValidationMetrics.total,
    correct: selected.selectionValidationMetrics.correct,
    accuracy: selected.selectionValidationMetrics.accuracy,
    wilson95Lower: selected.selectionValidationMetrics.wilson95_lower,
  });
  assert.deepEqual(zoneRegionExperiment.sealedTest, {
    total: selected.sealedMetrics.total,
    correct: selected.sealedMetrics.correct,
    accuracy: selected.sealedMetrics.accuracy,
    wilson95Lower: selected.sealedMetrics.wilson95_lower,
    wilson95Upper: selected.sealedMetrics.wilson95_upper,
    gate: selected.sealedMetrics.gate,
    passed: selected.sealedMetrics.passed,
    inferenceMillisecondsPerSample: selected.sealedMetrics.inferenceMillisecondsPerSample,
  });
});

