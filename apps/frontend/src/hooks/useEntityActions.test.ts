import { notifications } from "@mantine/notifications";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  useAssignRoomEntities,
  useDeleteEntities,
  useEntityState,
} from "./useEntityActions";

afterEach(() => {
  vi.restoreAllMocks();
});

function wrap(qc?: QueryClient) {
  const client =
    qc ?? new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client }, children);
}

function mockResults(
  results: Array<{ entity_id: string; ok: boolean; error?: string }>,
) {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ results }), {
      status: 200,
      headers: { "content-type": "application/json" },
    }),
  );
}

describe("useAssignRoomEntities", () => {
  it("POSTs entity_ids + area_id and shows aggregate toast", async () => {
    const fetchSpy = mockResults([
      { entity_id: "light.a", ok: true },
      { entity_id: "light.b", ok: true },
    ]);
    const showSpy = vi.spyOn(notifications, "show");
    const { result } = renderHook(() => useAssignRoomEntities(), {
      wrapper: wrap(),
    });
    await act(async () => {
      await result.current.mutateAsync({
        entity_ids: ["light.a", "light.b"],
        area_id: "kitchen",
      });
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const req = fetchSpy.mock.calls[0][0] as Request;
    expect(req.url).toContain("/api/actions/assign-room-entities");
    expect(await req.json()).toEqual({
      entity_ids: ["light.a", "light.b"],
      area_id: "kitchen",
    });
    expect(showSpy).toHaveBeenCalledWith(
      expect.objectContaining({ color: "green", message: "2 Updated" }),
    );
  });

  it("yellow toast on partial failure", async () => {
    mockResults([
      { entity_id: "light.a", ok: true },
      { entity_id: "light.b", ok: false, error: "x" },
    ]);
    const showSpy = vi.spyOn(notifications, "show");
    const { result } = renderHook(() => useAssignRoomEntities(), {
      wrapper: wrap(),
    });
    await act(async () => {
      await result.current.mutateAsync({
        entity_ids: ["light.a", "light.b"],
        area_id: "kitchen",
      });
    });
    expect(showSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        color: "yellow",
        message: "1 Updated, 1 Failed",
      }),
    );
  });

  it("invalidates the entities query on success", async () => {
    mockResults([{ entity_id: "light.a", ok: true }]);
    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const invalidate = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useAssignRoomEntities(), {
      wrapper: wrap(qc),
    });
    await act(async () => {
      await result.current.mutateAsync({
        entity_ids: ["light.a"],
        area_id: "kitchen",
      });
    });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["entities"] });
  });
});

describe("useEntityState", () => {
  it("POSTs {entity_ids, field, value}", async () => {
    const fetchSpy = mockResults([{ entity_id: "light.a", ok: true }]);
    const { result } = renderHook(() => useEntityState(), { wrapper: wrap() });
    await act(async () => {
      await result.current.mutateAsync({
        entity_ids: ["light.a"],
        field: "disabled_by",
        value: "user",
      });
    });
    const req = fetchSpy.mock.calls[0][0] as Request;
    expect(req.url).toContain("/api/actions/entity-state");
    expect(await req.json()).toEqual({
      entity_ids: ["light.a"],
      field: "disabled_by",
      value: "user",
    });
  });

  it("uses Disable-specific copy when field=disabled_by, value='user'", async () => {
    mockResults([{ entity_id: "light.a", ok: true }]);
    const showSpy = vi.spyOn(notifications, "show");
    const { result } = renderHook(() => useEntityState(), { wrapper: wrap() });
    await act(async () => {
      await result.current.mutateAsync({
        entity_ids: ["light.a"],
        field: "disabled_by",
        value: "user",
      });
    });
    expect(showSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Entity Disabled",
        message: "1 Disabled",
        color: "green",
      }),
    );
  });

  it("uses Enable-specific copy when field=disabled_by, value=null", async () => {
    mockResults([
      { entity_id: "a", ok: true },
      { entity_id: "b", ok: true },
    ]);
    const showSpy = vi.spyOn(notifications, "show");
    const { result } = renderHook(() => useEntityState(), { wrapper: wrap() });
    await act(async () => {
      await result.current.mutateAsync({
        entity_ids: ["a", "b"],
        field: "disabled_by",
        value: null,
      });
    });
    expect(showSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Entities Enabled",
        message: "2 Enabled",
      }),
    );
  });

  it("uses Hide/Show copy when field=hidden_by", async () => {
    mockResults([{ entity_id: "a", ok: true }]);
    const showSpy = vi.spyOn(notifications, "show");
    const { result } = renderHook(() => useEntityState(), { wrapper: wrap() });
    await act(async () => {
      await result.current.mutateAsync({
        entity_ids: ["a"],
        field: "hidden_by",
        value: "user",
      });
    });
    expect(showSpy).toHaveBeenCalledWith(
      expect.objectContaining({ title: "Entity Hidden", message: "1 Hidden" }),
    );
  });
});

describe("useDeleteEntities", () => {
  it("POSTs entity_ids and shows singular green toast", async () => {
    const fetchSpy = mockResults([{ entity_id: "light.a", ok: true }]);
    const showSpy = vi.spyOn(notifications, "show");
    const { result } = renderHook(() => useDeleteEntities(), {
      wrapper: wrap(),
    });
    await act(async () => {
      await result.current.mutateAsync(["light.a"]);
    });
    const req = fetchSpy.mock.calls[0][0] as Request;
    expect(req.url).toContain("/api/actions/delete-entity");
    expect(await req.json()).toEqual({ entity_ids: ["light.a"] });
    expect(showSpy).toHaveBeenCalledWith(
      expect.objectContaining({ color: "green", message: "Entity deleted" }),
    );
  });

  it("plural green toast when many succeed", async () => {
    mockResults([
      { entity_id: "a", ok: true },
      { entity_id: "b", ok: true },
    ]);
    const showSpy = vi.spyOn(notifications, "show");
    const { result } = renderHook(() => useDeleteEntities(), {
      wrapper: wrap(),
    });
    await act(async () => {
      await result.current.mutateAsync(["a", "b"]);
    });
    expect(showSpy).toHaveBeenCalledWith(
      expect.objectContaining({ color: "green", message: "2 entities deleted" }),
    );
  });

  it("yellow partial toast", async () => {
    mockResults([
      { entity_id: "a", ok: true },
      { entity_id: "b", ok: false, error: "refused" },
    ]);
    const showSpy = vi.spyOn(notifications, "show");
    const { result } = renderHook(() => useDeleteEntities(), {
      wrapper: wrap(),
    });
    await act(async () => {
      await result.current.mutateAsync(["a", "b"]);
    });
    expect(showSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        color: "yellow",
        message: "1 deleted, 1 failed",
      }),
    );
  });

  it("red toast with backend error when all fail", async () => {
    mockResults([
      { entity_id: "a", ok: false, error: "integration refused removal" },
    ]);
    const showSpy = vi.spyOn(notifications, "show");
    const { result } = renderHook(() => useDeleteEntities(), {
      wrapper: wrap(),
    });
    await act(async () => {
      await result.current.mutateAsync(["a"]);
    });
    expect(showSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        color: "red",
        message: "integration refused removal",
      }),
    );
  });
});
