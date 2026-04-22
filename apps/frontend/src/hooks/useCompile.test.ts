import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useCompile } from "./useCompile";

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children);
}

describe("useCompile", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(async (req: Request) => {
      const url = typeof req === "string" ? req : req.url;
      expect(url).toContain("/api/policies/compile");
      const method = typeof req === "string" ? "GET" : req.method;
      expect(method).toBe("POST");
      return new Response(JSON.stringify({ ok: true, error: null, position: null }), { status: 200 });
    }));
  });

  it("posts the draft and returns ok", async () => {
    const { result } = renderHook(() => useCompile(), { wrapper: wrap() });
    await act(async () => {
      await result.current.mutateAsync({
        id: "t", type: "custom", scope: "devices", severity: "info",
        when: "true", assert: "true", message: "m",
      } as any);
    });
    await waitFor(() => expect(result.current.data?.ok).toBe(true));
  });
});
