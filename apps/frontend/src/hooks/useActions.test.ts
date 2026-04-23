import { notifications } from "@mantine/notifications";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useUpdateDevice } from "./useActions";

afterEach(() => {
  vi.restoreAllMocks();
});

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children);
}

describe("useUpdateDevice", () => {
  it("PATCHes only the fields provided", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    const { result } = renderHook(() => useUpdateDevice(), { wrapper: wrap() });
    await act(async () => {
      await result.current.mutateAsync({
        device_id: "d1",
        changes: { name_by_user: "New Name" },
      });
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const req = fetchSpy.mock.calls[0][0] as Request;
    expect(req.method).toBe("PATCH");
    expect(req.url).toContain("/api/actions/device/d1");
    const body = await req.json();
    expect(body).toEqual({ name_by_user: "New Name" });
  });

  it("propagates backend errors", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "ha update failed: boom" }), {
        status: 502,
        headers: { "content-type": "application/json" },
      }),
    );

    const { result } = renderHook(() => useUpdateDevice(), { wrapper: wrap() });
    await expect(
      act(async () => {
        await result.current.mutateAsync({
          device_id: "d1",
          changes: { name_by_user: "x" },
        });
      }),
    ).rejects.toThrow();
  });

  it("shows a success notification on 200", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    const showSpy = vi.spyOn(notifications, "show");

    const { result } = renderHook(() => useUpdateDevice(), { wrapper: wrap() });
    await act(async () => {
      await result.current.mutateAsync({
        device_id: "d1",
        changes: { name_by_user: "x" },
      });
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(showSpy).toHaveBeenCalledWith(
      expect.objectContaining({ color: "green" }),
    );
  });

  it("shows an error notification on failure", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "ha update failed" }), {
        status: 502,
        headers: { "content-type": "application/json" },
      }),
    );
    const showSpy = vi.spyOn(notifications, "show");

    const { result } = renderHook(() => useUpdateDevice(), { wrapper: wrap() });
    await expect(
      act(async () => {
        await result.current.mutateAsync({
          device_id: "d1",
          changes: { name_by_user: "x" },
        });
      }),
    ).rejects.toThrow();

    await waitFor(() =>
      expect(showSpy).toHaveBeenCalledWith(
        expect.objectContaining({ color: "red" }),
      ),
    );
  });
});
