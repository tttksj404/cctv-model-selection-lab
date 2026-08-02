import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "./httpClient";
import { listAuditLogs } from "./auditLogApi";

const originalAdapter = apiClient.defaults.adapter;

const response = (config, data) => ({
  config,
  data,
  headers: {},
  request: {},
  status: 200,
  statusText: "OK"
});

describe("auditLogApi", () => {
  afterEach(() => {
    apiClient.defaults.adapter = originalAdapter;
  });

  it("calls the audit-log endpoint with server-side query parameters", async () => {
    const adapter = vi.fn(async (config) => response(config, {
      timestamp: "2026-08-02T01:00:00Z",
      data: [{ id: 1, actionType: "CASE_STATUS_CHANGED" }],
      meta: { page: 1, size: 10, totalElements: 11, totalPages: 2, sort: "createdAt,desc" }
    }));
    apiClient.defaults.adapter = adapter;

    await expect(listAuditLogs({
      caseId: 20,
      actionType: "CASE_STATUS_CHANGED",
      actor: "Administrator",
      from: "2026-08-02T01:00:00.000Z",
      to: "2026-08-02T02:00:00.000Z",
      page: 1,
      size: 10,
      sort: "createdAt,desc"
    })).resolves.toEqual({
      data: [{ id: 1, actionType: "CASE_STATUS_CHANGED" }],
      meta: { page: 1, size: 10, totalElements: 11, totalPages: 2, sort: "createdAt,desc" }
    });

    expect(adapter).toHaveBeenCalledWith(expect.objectContaining({
      method: "get",
      url: "/admin/audit-logs",
      params: expect.objectContaining({
        caseId: 20,
        actionType: "CASE_STATUS_CHANGED",
        actor: "Administrator",
        page: 1,
        size: 10,
        sort: "createdAt,desc"
      })
    }));
  });
});
