import { apiClient, unwrapData, unwrapPagedData } from "./httpClient";

const casePath = (caseId, suffix = "") => `/admin/cases/${encodeURIComponent(caseId)}${suffix}`;

export async function listCases(params = {}) {
  return unwrapPagedData(await apiClient.get("/admin/cases", { params }));
}

export async function getCase(caseId) {
  return unwrapData(await apiClient.get(casePath(caseId)));
}

export async function createCase(payload) {
  return unwrapData(await apiClient.post("/admin/cases", payload));
}

export async function updateCase(caseId, patch) {
  return unwrapData(await apiClient.patch(casePath(caseId), patch));
}

export async function putCasePhoto(caseId, photo) {
  const body = new FormData();
  body.append("photo", photo);

  // Let the browser add the multipart boundary. Setting Content-Type here would omit it.
  return unwrapData(await apiClient.put(casePath(caseId, "/photo"), body));
}

export async function deleteCasePhoto(caseId) {
  return unwrapData(await apiClient.delete(casePath(caseId, "/photo")));
}

export async function updateCaseStatus(caseId, payload) {
  return unwrapData(await apiClient.patch(casePath(caseId, "/status"), payload));
}

export async function closeCase(caseId, payload) {
  return unwrapData(await apiClient.post(casePath(caseId, "/close"), payload));
}

export async function listSearchConditions(caseId) {
  return unwrapData(await apiClient.get(casePath(caseId, "/search-conditions")));
}

export async function createSearchCondition(caseId, payload) {
  return unwrapData(await apiClient.post(casePath(caseId, "/search-conditions"), payload));
}

export async function replaceSearchCondition(caseId, conditionId, payload) {
  const conditionPath = `/search-conditions/${encodeURIComponent(conditionId)}`;
  return unwrapData(await apiClient.put(casePath(caseId, conditionPath), payload));
}

export async function deleteSearchCondition(caseId, conditionId) {
  const conditionPath = `/search-conditions/${encodeURIComponent(conditionId)}`;
  return unwrapData(await apiClient.delete(casePath(caseId, conditionPath)));
}

export async function listCaseCameras(caseId) {
  return unwrapData(await apiClient.get(casePath(caseId, "/cameras")));
}

export async function addCaseCameras(caseId, cameraIds) {
  return unwrapData(await apiClient.post(casePath(caseId, "/cameras"), { cameraIds }));
}

export async function removeCaseCamera(caseId, cameraId) {
  const cameraSuffix = `/cameras/${encodeURIComponent(cameraId)}`;
  return unwrapData(await apiClient.delete(casePath(caseId, cameraSuffix)));
}
