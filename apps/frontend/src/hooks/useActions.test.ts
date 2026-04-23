import { notifications } from "@mantine/notifications";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useDeleteDevices, useUpdateDevice } from "./useActions";

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

describe("useDeleteDevices", () => {
  function mockResults(
    results: Array<{ device_id: string; ok: boolean; error?: string }>,
  ) {
    return vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ results }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
  }

  it("POSTs device_ids and returns the results", async () => {
    const fetchSpy = mockResults([{ device_id: "d1", ok: true }]);
    const { result } = renderHook(() => useDeleteDevices(), { wrapper: wrap() });
    await act(async () => {
      await result.current.mutateAsync(["d1"]);
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const req = fetchSpy.mock.calls[0][0] as Request;
    expect(req.method).toBe("POST");
    expect(req.url).toContain("/api/actions/delete");
    expect(await req.json()).toEqual({ device_ids: ["d1"] });
  });

  it("shows singular success toast for one device", async () => {
    mockResults([{ device_id: "d1", ok: true }]);
    const showSpy = vi.spyOn(notifications, "show");
    const { result } = renderHook(() => useDeleteDevices(), { wrapper: wrap() });
    await act(async () => {
      await result.current.mutateAsync(["d1"]);
    });
    expect(showSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        color: "green",
        message: "Device deleted",
      }),
    );
  });

  it("shows plural success toast for many devices", async () => {
    mockResults([
      { device_id: "d1", ok: true },
      { device_id: "d2", ok: true },
    ]);
    const showSpy = vi.spyOn(notifications, "show");
    const { result } = renderHook(() => useDeleteDevices(), { wrapper: wrap() });
    await act(async () => {
      await result.current.mutateAsync(["d1", "d2"]);
    });
    expect(showSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        color: "green",
        message: "2 devices deleted",
      }),
    );
  });

  it("shows yellow partial toast", async () => {
    mockResults([
      { device_id: "d1", ok: true },
      { device_id: "d2", ok: false, error: "refused" },
    ]);
    const showSpy = vi.spyOn(notifications, "show");
    const { result } = renderHook(() => useDeleteDevices(), { wrapper: wrap() });
    await act(async () => {
      await result.current.mutateAsync(["d1", "d2"]);
    });
    expect(showSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        color: "yellow",
        message: "1 deleted, 1 failed",
      }),
    );
  });

  it("shows single-fail red toast with the backend error", async () => {
    mockResults([{ device_id: "d1", ok: false, error: "integration refused removal" }]);
    const showSpy = vi.spyOn(notifications, "show");
    const { result } = renderHook(() => useDeleteDevices(), { wrapper: wrap() });
    await act(async () => {
      await result.current.mutateAsync(["d1"]);
    });
    expect(showSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        color: "red",
        message: "integration refused removal",
      }),
    );
  });
});
