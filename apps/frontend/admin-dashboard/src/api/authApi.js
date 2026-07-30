import { apiClient, issueCsrfToken, unwrapData } from "./httpClient";

export { issueCsrfToken } from "./httpClient";

async function refreshCsrfTokenBestEffort() {
  try {
    await issueCsrfToken({ force: true });
  } catch {
    // Authentication already succeeded; token refresh failure is recoverable on the next mutation.
  }
}

export async function login({ loginId, password }) {
  const response = await apiClient.post(
    "/auth/admin/login",
    { loginId, password },
    { skipUnauthorizedHandler: true }
  );
  const admin = unwrapData(response);
  await refreshCsrfTokenBestEffort();
  return admin;
}

export async function getCurrentAdmin() {
  return unwrapData(await apiClient.get("/admins/me"));
}

export async function logout() {
  await apiClient.post("/auth/admin/logout");
  await refreshCsrfTokenBestEffort();
}
