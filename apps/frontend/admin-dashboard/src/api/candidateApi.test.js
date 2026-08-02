import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchAdminCandidates } from "./candidateApi";
import { apiClient } from "./httpClient";

const originalAdapter = apiClient.defaults.adapter;

afterEach(() => {
  apiClient.defaults.adapter = originalAdapter;
});

describe("candidateApi", () => {
  it("백엔드가 발급한 서명 URL을 그대로 반환하고 ETag 캐시를 사용하지 않는다", async () => {
    const adapter = vi.fn(async (config) => ({
      config,
      data: {
        data: [{
          id: 1,
          frameUrl: "https://storage.example/frame?signature=frame",
          cropUrl: "https://storage.example/crop?signature=crop"
        }],
        meta: { page: 0, size: 20, totalElements: 1, totalPages: 1 }
      },
      headers: {},
      request: {},
      status: 200,
      statusText: "OK"
    }));
    apiClient.defaults.adapter = adapter;

    await expect(fetchAdminCandidates({ page: 0, size: 20 })).resolves.toEqual({
      rows: [{
        id: 1,
        frameUrl: "https://storage.example/frame?signature=frame",
        cropUrl: "https://storage.example/crop?signature=crop"
      }],
      meta: { page: 0, size: 20, totalElements: 1, totalPages: 1 }
    });

    expect(adapter.mock.calls[0][0]).toMatchObject({
      method: "get",
      url: "/admin/candidates",
      params: { page: 0, size: 20 }
    });
    expect(adapter.mock.calls[0][0].headers["If-None-Match"]).toBeUndefined();
  });
});
