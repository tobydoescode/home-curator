import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useExceptionsList } from "./useExceptions";

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children);
}

describe("useExceptionsList", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(async (req: Request) => {
      const url = typeof req === "string" ? req : req.url;
      expect(url).toContain("/api/exceptions/list");
      return new Response(JSON.stringify({
        exceptions: [{ id: 1, device_id: "d1", policy_id: "p1", acknowledged_at: "2026-04-22T00:00:00Z" }],
        total: 1, page: 1, page_size: 50,
      }), { status: 200 });
    }));
  });

  it("fetches and returns rows", async () => {
    const { result } = renderHook(() => useExceptionsList({ page: 1, page_size: 50 }), { wrapper: wrap() });
    await waitFor(() => expect(result.current.data?.total).toBe(1));
  });
});
