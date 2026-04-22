import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useSimulate } from "./useSimulate";

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children);
}

describe("useSimulate", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(async (req: Request) => {
      const url = typeof req === "string" ? req : req.url;
      expect(url).toContain("/api/policies/simulate");
      return new Response(JSON.stringify({
        ok: true, error: null,
        counts: { matched_when: 1, passes_assert: 0, fails_assert: 1, errored: 0 },
        failing: [{ id: "d1", name: "foo", room: null, message: "m" }],
        errored: [], passing: [],
      }), { status: 200 });
    }));
  });

  it("runs with a draft policy", async () => {
    const { result } = renderHook(() => useSimulate(), { wrapper: wrap() });
    await act(async () => {
      await result.current.mutateAsync({ policy: { id: "t", type: "custom" } as any });
    });
    await waitFor(() => expect(result.current.data?.counts?.fails_assert).toBe(1));
  });
});
