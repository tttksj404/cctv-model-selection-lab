import { apiClient, unwrapData, unwrapPagedData } from "./httpClient";

export async function listAdminRecordings(params = {}) {
  return unwrapPagedData(await apiClient.get("/admin/recordings", { params }));
}

const analysisJobPath = (caseId, suffix = "") =>
  `/admin/cases/${encodeURIComponent(caseId)}/recording-analysis-jobs${suffix}`;

export async function createRecordingAnalysisJob(caseId, payload) {
  return unwrapData(await apiClient.post(analysisJobPath(caseId), payload));
}

export async function fetchRecordingAnalysisJob(caseId, jobId) {
  return unwrapData(await apiClient.get(analysisJobPath(caseId, `/${encodeURIComponent(jobId)}`)));
}
