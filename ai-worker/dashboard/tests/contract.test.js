import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import YAML from "yaml";

import { validateProbabilityResponse } from "../domain.js";
import { mockScenarios } from "../mock-data.js";

const contractUrl = new URL("../contracts/zone-dashboard-proxy.openapi.yaml", import.meta.url);

async function readContract() {
  return YAML.parse(await readFile(contractUrl, "utf8"));
}

test("future proxy contract stays under the existing admin case namespace", async () => {
  const contract = await readContract();
  const path = contract.paths["/api/v1/admin/cases/{caseId}/ai-search/zone-probability"];
  assert.ok(path?.get);
  const caseId = path.get.parameters.find((parameter) => parameter.name === "caseId");
  assert.deepEqual(caseId.schema, { type: "integer", format: "int64", minimum: 1 });
});

test("future proxy uses the central session and ApiResponse conventions", async () => {
  const contract = await readContract();
  const operation =
    contract.paths["/api/v1/admin/cases/{caseId}/ai-search/zone-probability"].get;
  assert.deepEqual(operation.security, [{ sessionCookie: [] }]);
  assert.equal(contract.components.securitySchemes.sessionCookie.name, "EYESONU_SESSION");
  assert.equal(
    operation.responses[200].content["application/json"].schema.$ref,
    "#/components/schemas/ApiResponseZoneProbabilityView",
  );
  assert.ok(operation.responses[401]);
  assert.ok(operation.responses[403]);
  assert.deepEqual(
    contract.components.schemas.ApiResponseZoneProbabilityView.required,
    ["timestamp", "data"],
  );
});

test("future proxy contract contains every field consumed by the dashboard", async () => {
  const contract = await readContract();
  const view = contract.components.schemas.ZoneProbabilityView;
  const required = new Set(view.required);
  for (const field of [
    "candidateAssessments",
    "candidatePoolStatus",
    "zoneCandidateSummaries",
    "mostLikelyZoneId",
    "mostLikelyZoneProbability",
    "posteriorEntropy",
    "cameraSelectionPolicy",
  ]) {
    assert.ok(required.has(field), `${field} must be required`);
  }
  assert.deepEqual(view.properties.caseId, { type: "integer", format: "int64", minimum: 1 });
  assert.equal(validateProbabilityResponse(mockScenarios.current), mockScenarios.current);
  assert.ok(Number.isSafeInteger(mockScenarios.current.caseId));
  for (const zoneId of [1, 2, 3, 4]) {
    assert.ok(contract.components.schemas[`ZonePosterior${zoneId}`]);
    assert.ok(contract.components.schemas[`ZoneCandidateSummary${zoneId}`]);
  }
});

