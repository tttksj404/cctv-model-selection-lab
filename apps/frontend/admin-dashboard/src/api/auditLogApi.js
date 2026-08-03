import { apiClient, unwrapPagedData } from "./httpClient";

export async function listAuditLogs(params = {}) {
  return unwrapPagedData(await apiClient.get("/admin/audit-logs", { params }));
}
