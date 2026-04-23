import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useEntities } from "./useEntities";

afterEach(() => {
  vi.restoreAllMocks();
});

function wrap() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children);
}

describe("useEntities", () => {
  it("hits /api/entities and returns the typed payload", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          entities: [
            {
              entity_id: "light.kitchen_lamp",
              name: "Kitchen Lamp",
              original_name: null,
              display_name: "Kitchen Lamp",
              domain: "light",
              platform: "hue",
              device_id: "d1",
              device_name: "Hue Bulb",
              area_id: "kitchen",
              area_name: "Kitchen",
              disabled_by: null,
              hidden_by: null,
              icon: null,
              created_at: null,
              modified_at: null,
              issue_count: 0,
              highest_severity: null,
              issues: [],
            },
          ],
          total: 1,
          page: 1,
          page_size: 50,
          issue_counts_by_type: {},
          domain_counts: { light: 1 },
          area_counts: {},
          integration_counts: { hue: 1 },
          all_domains: ["light"],
          all_areas: [{ id: "kitchen", name: "Kitchen" }],
          all_integrations: ["hue"],
          all_issue_types: [],
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      ),
    );

    const { result } = renderHook(
      () => useEntities({ q: "lamp", page: 1, page_size: 50 }),
      { wrapper: wrap() },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.total).toBe(1);
    expect(result.current.data?.entities[0].entity_id).toBe("light.kitchen_lamp");

    const req = fetchSpy.mock.calls[0][0] as Request;
    expect(req.url).toContain("/api/entities");
    expect(req.url).toContain("q=lamp");
  });

  it("uses ['entities', params] as the query key", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ entities: [], total: 0, page: 1, page_size: 50 }),
        {
          status: 200,
          headers: { "content-type": "application/json" },
        },
      ),
    );

    // Two distinct param objects produce two cache entries — assert via
    // the React Query cache rather than internal hook state.
    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const wrapper = ({ children }: { children: React.ReactNode }) =>
      React.createElement(QueryClientProvider, { client: qc }, children);

    renderHook(() => useEntities({ page: 1 }), { wrapper });
    renderHook(() => useEntities({ page: 2 }), { wrapper });

    await waitFor(() => {
      const keys = qc.getQueryCache().getAll().map((q) => q.queryKey);
      expect(keys.some((k) => Array.isArray(k) && k[0] === "entities")).toBe(true);
      expect(keys.length).toBeGreaterThanOrEqual(2);
    });
  });
});
