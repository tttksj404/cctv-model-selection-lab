import client from "./httpClient";

export async function fetchAdminCandidates(params = {}) {
  const response = await client.get("/admin/candidates", {
    params
  });

  const data = response.data || {};
  return { rows: data.data || [], meta: data.meta || {} };
}

export async function fetchAdminCandidate(candidateId) {
  const { data } = await client.get(`/admin/candidates/${candidateId}`);
  return data.data;
}

export async function reviewAdminCandidate(candidateId, payload) {
  const { data } = await client.patch(`/admin/candidates/${candidateId}/review`, payload);
  return data.data;
}
