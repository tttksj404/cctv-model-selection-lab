import client from "./httpClient";

export async function fetchAdminCandidates(params = {}) {
  const { data } = await client.get("/api/v1/admin/candidates", { params });
  return { rows: data.data || [], meta: data.meta || {} };
}

export async function fetchAdminCandidate(candidateId) {
  const { data } = await client.get(`/api/v1/admin/candidates/${candidateId}`);
  return data.data;
}

export function objectUrl(objectKey) {
  if (!objectKey) return "";
  const base = import.meta.env.VITE_STORAGE_PUBLIC_URL;
  return base ? `${base.replace(/\/$/, "")}/${objectKey}` : "";
}
