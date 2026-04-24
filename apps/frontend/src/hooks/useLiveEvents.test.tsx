import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { PropsWithChildren } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { SSEEvent } from "@/api/sse";
import { useLiveEvents } from "./useLiveEvents";

let handler: ((event: SSEEvent) => void) | null = null;
const unsubscribe = vi.fn();

vi.mock("@/api/sse", () => ({
  subscribeSSE: vi.fn((cb: (event: SSEEvent) => void) => {
    handler = cb;
    return unsubscribe;
  }),
}));

function wrapperWith(client: QueryClient) {
  return function Wrapper({ children }: PropsWithChildren) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

describe("useLiveEvents", () => {
  afterEach(() => {
    handler = null;
    unsubscribe.mockClear();
    vi.unstubAllGlobals();
  });

  it("does nothing when EventSource is unavailable", () => {
    vi.stubGlobal("EventSource", undefined);
    const qc = new QueryClient();
    const invalidate = vi.spyOn(qc, "invalidateQueries");

    renderHook(() => useLiveEvents(), { wrapper: wrapperWith(qc) });

    expect(invalidate).not.toHaveBeenCalled();
    expect(handler).toBeNull();
  });

  it("invalidates devices, policies, and entities for matching events", async () => {
    vi.stubGlobal("EventSource", class {});
    const qc = new QueryClient();
    const invalidate = vi.spyOn(qc, "invalidateQueries");
    const { result, unmount } = renderHook(() => useLiveEvents(), {
      wrapper: wrapperWith(qc),
    });

    act(() => {
      handler?.({ kind: "devices_changed" });
      handler?.({ kind: "policies_changed" });
      handler?.({ kind: "entity_updated", entity_id: "light.kitchen" });
      handler?.({ kind: "entity_deleted", entity_id: "light.kitchen" });
      handler?.({ kind: "entities_changed" });
    });

    await waitFor(() => expect(result.current.lastEventAt).not.toBeNull());
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["devices"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["policies"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["entities"] });

    unmount();
    expect(unsubscribe).toHaveBeenCalledTimes(1);
  });
});
