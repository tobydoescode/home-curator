import { afterEach, describe, expect, it, vi } from "vitest";

import { subscribeSSE } from "./sse";

class MockEventSource {
  static instances: MockEventSource[] = [];
  listeners = new Map<string, (event: MessageEvent | Event) => void>();
  close = vi.fn();
  url: string;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: (event: MessageEvent | Event) => void) {
    this.listeners.set(type, listener);
  }

  emitMessage(data: string) {
    this.listeners.get("message")?.({ data } as MessageEvent);
  }

  emitError() {
    this.listeners.get("error")?.(new Event("error"));
  }
}

describe("subscribeSSE", () => {
  afterEach(() => {
    MockEventSource.instances = [];
    vi.unstubAllGlobals();
  });

  it("subscribes to /api/events and emits parsed messages", () => {
    vi.stubGlobal("EventSource", MockEventSource);
    const onEvent = vi.fn();
    const unsubscribe = subscribeSSE(onEvent);
    const source = MockEventSource.instances[0];

    expect(source.url).toBe("/api/events");
    source.emitMessage('{"kind":"devices_changed"}');

    expect(onEvent).toHaveBeenCalledWith({ kind: "devices_changed" });
    unsubscribe();
    expect(source.close).toHaveBeenCalledTimes(1);
  });

  it("calls onError for invalid JSON and EventSource errors", () => {
    vi.stubGlobal("EventSource", MockEventSource);
    const onEvent = vi.fn();
    const onError = vi.fn();
    subscribeSSE(onEvent, onError);
    const source = MockEventSource.instances[0];

    source.emitMessage("{not-json");
    source.emitError();

    expect(onEvent).not.toHaveBeenCalled();
    expect(onError).toHaveBeenCalledTimes(2);
  });
});
