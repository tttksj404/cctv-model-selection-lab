import { apiClient, unwrapData } from "./httpClient";

const adminPath = (adminId, suffix = "") =>
  `/admins/${encodeURIComponent(adminId)}${suffix}`;

export async function listAdmins() {
  return unwrapData(await apiClient.get("/admins"));
}

export async function createAdmin({ loginId, name, password }) {
  return unwrapData(await apiClient.post("/admins", { loginId, name, password }));
}

export async function updateAdminStatus(adminId, enabled) {
  return unwrapData(await apiClient.patch(adminPath(adminId, "/status"), { enabled }));
}
