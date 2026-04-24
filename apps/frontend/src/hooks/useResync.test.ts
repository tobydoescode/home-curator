import { notifications } from "@mantine/notifications";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useResync } from "./useResync";

afterEach(() => {
  vi.restoreAllMocks();
});

function wrap(qc: QueryClient) {
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children);
}

function mockOk(body: {
  added: number;
  removed: number;
  updated: number;
  entity_added?: number;
  entity_removed?: number;
  entity_updated?: number;
}) {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify(body), {
      status: 200,
      headers: { "content-type": "application/json" },
    }),
  );
}

describe("useResync", () => {
  it("POSTs /api/cache/resync with no body", async () => {
    const fetchSpy = mockOk({ added: 0, removed: 0, updated: 0 });
    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const { result } = renderHook(() => useResync(), { wrapper: wrap(qc) });
    await act(async () => {
      await result.current.mutateAsync();
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const req = fetchSpy.mock.calls[0][0] as Request;
    expect(req.method).toBe("POST");
    expect(req.url).toContain("/api/cache/resync");
  });

  it("invalidates devices, entities and policies on success", async () => {
    mockOk({ added: 0, removed: 0, updated: 0 });
    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const invalidateSpy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useResync(), { wrapper: wrap(qc) });
    await act(async () => {
      await result.current.mutateAsync();
    });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["devices"] });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["entities"] });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["policies"] });
  });

  it("shows a green toast with 'Resynced' when the diff is empty", async () => {
    mockOk({ added: 0, removed: 0, updated: 0 });
    const showSpy = vi.spyOn(notifications, "show");
    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const { result } = renderHook(() => useResync(), { wrapper: wrap(qc) });
    await act(async () => {
      await result.current.mutateAsync();
    });
    expect(showSpy).toHaveBeenCalledWith(
      expect.objectContaining({ color: "green", message: "Resynced" }),
    );
  });

  it("shows a green toast with a change count when the diff is non-empty", async () => {
    mockOk({ added: 1, removed: 0, updated: 2 });
    const showSpy = vi.spyOn(notifications, "show");
    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const { result } = renderHook(() => useResync(), { wrapper: wrap(qc) });
    await act(async () => {
      await result.current.mutateAsync();
    });
    expect(showSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        color: "green",
        message: "Resynced — 3 changes detected",
      }),
    );
  });

  it("uses singular copy when exactly one changed", async () => {
    mockOk({ added: 1, removed: 0, updated: 0 });
    const showSpy = vi.spyOn(notifications, "show");
    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const { result } = renderHook(() => useResync(), { wrapper: wrap(qc) });
    await act(async () => {
      await result.current.mutateAsync();
    });
    expect(showSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        color: "green",
        message: "Resynced — 1 change detected",
      }),
    );
  });

  it("shows a red toast and does not invalidate on failure", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "resync failed: ha unavailable" }), {
        status: 502,
        headers: { "content-type": "application/json" },
      }),
    );
    const showSpy = vi.spyOn(notifications, "show");
    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const invalidateSpy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useResync(), { wrapper: wrap(qc) });
    await expect(
      act(async () => {
        await result.current.mutateAsync();
      }),
    ).rejects.toThrow();
    await waitFor(() =>
      expect(showSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          color: "red",
          title: "Resync Failed",
          message: "resync failed: ha unavailable",
        }),
      ),
    );
    expect(invalidateSpy).not.toHaveBeenCalled();
  });
});
