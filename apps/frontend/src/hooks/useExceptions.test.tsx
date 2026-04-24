import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { PropsWithChildren } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "@/api/client";
import {
  useBulkDeleteExceptions,
  useClearException,
  useExceptionsForDevice,
} from "./useExceptions";

vi.mock("@/api/client", () => ({
  api: {
    DELETE: vi.fn(),
    GET: vi.fn(),
    POST: vi.fn(),
  },
}));

function wrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: PropsWithChildren) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

describe("useExceptions hooks", () => {
  beforeEach(() => vi.clearAllMocks());

  it("clears device exceptions via the device endpoint", async () => {
    vi.mocked(api.DELETE).mockResolvedValue({ data: {}, error: undefined } as any);
    const { result } = renderHook(() => useClearException(), { wrapper: wrapper() });

    await result.current.mutateAsync({ device_id: "dev-1", policy_id: "missing-room" });

    expect(api.DELETE).toHaveBeenCalledWith(
      "/api/exceptions/device/{device_id}/{policy_id}",
      { params: { path: { device_id: "dev-1", policy_id: "missing-room" } } },
    );
  });

  it("clears entity exceptions via the entity endpoint", async () => {
    vi.mocked(api.DELETE).mockResolvedValue({ data: {}, error: undefined } as any);
    const { result } = renderHook(() => useClearException(), { wrapper: wrapper() });

    await result.current.mutateAsync({
      entity_id: "light.kitchen",
      policy_id: "bad-name",
    });

    expect(api.DELETE).toHaveBeenCalledWith(
      "/api/exceptions/entity/{entity_id}/{policy_id}",
      { params: { path: { entity_id: "light.kitchen", policy_id: "bad-name" } } },
    );
  });

  it("rejects clear exception without a device or entity id", async () => {
    const { result } = renderHook(() => useClearException(), { wrapper: wrapper() });

    await expect(result.current.mutateAsync({ policy_id: "missing-room" })).rejects.toThrow(
      "device_id or entity_id required",
    );
  });

  it("loads exceptions for a device when enabled", async () => {
    vi.mocked(api.GET).mockResolvedValue({ data: [{ id: 1 }], error: undefined } as any);
    const { result } = renderHook(() => useExceptionsForDevice("dev-1"), {
      wrapper: wrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.GET).toHaveBeenCalledWith("/api/exceptions", {
      params: { query: { device_id: "dev-1" } },
    });
  });

  it("bulk deletes exceptions and returns backend data", async () => {
    vi.mocked(api.POST).mockResolvedValue({ data: { deleted: 2 }, error: undefined } as any);
    const { result } = renderHook(() => useBulkDeleteExceptions(), { wrapper: wrapper() });

    await expect(result.current.mutateAsync([1, 2])).resolves.toEqual({ deleted: 2 });
    expect(api.POST).toHaveBeenCalledWith("/api/exceptions/bulk-delete", {
      body: { ids: [1, 2] },
    });
  });
});
