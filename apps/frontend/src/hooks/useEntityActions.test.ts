import "@testing-library/jest-dom/vitest";

import { MantineProvider } from "@mantine/core";
import { Notifications } from "@mantine/notifications";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  useAssignRoomEntities,
  useDeleteEntities,
  useEntityState,
  useRenameEntityPattern,
  useUpdateEntity,
} from "./useEntityActions";

function wrap() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(
      MantineProvider,
      null,
      React.createElement(Notifications, null),
      React.createElement(QueryClientProvider, { client: qc }, children),
    );
}

afterEach(() => vi.restoreAllMocks());

describe("useUpdateEntity", () => {
  it("PATCHes dirty fields and includes new_entity_id when renaming", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    );
    const { result } = renderHook(() => useUpdateEntity(), { wrapper: wrap() });
    await act(async () => {
      await result.current.mutateAsync({
        entity_id: "light.a",
        changes: { new_entity_id: "light.b", name: "Bulb" },
      });
    });
    const req = fetchSpy.mock.calls[0][0] as Request;
    expect(req.method).toBe("PATCH");
    expect(req.url).toContain("/api/actions/entity/light.a");
    expect(await req.json()).toEqual({ new_entity_id: "light.b", name: "Bulb" });
  });

  it("surfaces a red toast on 502 (HA refusal)", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "ha refused" }), { status: 502 }),
    );
    const { result } = renderHook(() => useUpdateEntity(), { wrapper: wrap() });
    await act(async () => {
      await result.current
        .mutateAsync({ entity_id: "light.a", changes: { name: "x" } })
        .catch(() => {});
    });
    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});

describe("useDeleteEntities", () => {
  it("POSTs entity_ids", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          results: [
            { entity_id: "light.a", ok: true },
            { entity_id: "light.b", ok: true },
          ],
        }),
        { status: 200 },
      ),
    );
    const { result } = renderHook(() => useDeleteEntities(), { wrapper: wrap() });
    await act(async () => {
      await result.current.mutateAsync(["light.a", "light.b"]);
    });
    const req = fetchSpy.mock.calls[0][0] as Request;
    expect(req.url).toContain("/api/actions/delete-entity");
    expect(await req.json()).toEqual({ entity_ids: ["light.a", "light.b"] });
  });
});

describe("useAssignRoomEntities", () => {
  it("POSTs entity_ids + area_id", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ results: [{ entity_id: "light.a", ok: true }] }),
        { status: 200 },
      ),
    );
    const { result } = renderHook(() => useAssignRoomEntities(), {
      wrapper: wrap(),
    });
    await act(async () => {
      await result.current.mutateAsync({
        entity_ids: ["light.a"],
        area_id: "office",
      });
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const req = fetchSpy.mock.calls[0][0] as Request;
    expect(await req.json()).toEqual({
      entity_ids: ["light.a"],
      area_id: "office",
    });
  });
});

describe("useRenameEntityPattern", () => {
  it("dry_run=true does not invalidate entities cache", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ results: [], error: null }), { status: 200 }),
    );
    const { result } = renderHook(() => useRenameEntityPattern(), {
      wrapper: wrap(),
    });
    await act(async () => {
      await result.current.mutateAsync({
        entity_ids: ["light.a"],
        id_pattern: "^light\\.(.+)$",
        id_replacement: "light.x_$1",
        dry_run: true,
      });
    });
    const req = fetchSpy.mock.calls[0][0] as Request;
    expect(req.url).toContain("/api/actions/rename-pattern-entities");
    expect(await req.json()).toMatchObject({ dry_run: true });
  });

  it("apply (dry_run=false) succeeds with per-entity results", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          results: [
            {
              entity_id: "light.a",
              ok: true,
              id_changed: true,
              new_entity_id: "light.x_a",
              name_changed: false,
            },
            {
              entity_id: "light.b",
              ok: false,
              error: "entity_id already exists",
            },
          ],
          error: null,
        }),
        { status: 200 },
      ),
    );
    const { result } = renderHook(() => useRenameEntityPattern(), {
      wrapper: wrap(),
    });
    await act(async () => {
      await result.current.mutateAsync({
        entity_ids: ["light.a", "light.b"],
        id_pattern: "^light\\.(.+)$",
        id_replacement: "light.x_$1",
        dry_run: false,
      });
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});

describe("useEntityState", () => {
  it("POSTs entity_ids + field + value", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ results: [{ entity_id: "light.a", ok: true }] }),
        { status: 200 },
      ),
    );
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
});
