import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { useLocalStorageBoolean } from "./useLocalStorageBoolean";

const KEY = "test:flag";

afterEach(() => {
  localStorage.clear();
});

describe("useLocalStorageBoolean", () => {
  it("returns the default value when localStorage has no entry", () => {
    const { result } = renderHook(() => useLocalStorageBoolean(KEY, true));
    expect(result.current[0]).toBe(true);
  });

  it("reads an existing value from localStorage", () => {
    localStorage.setItem(KEY, "false");
    const { result } = renderHook(() => useLocalStorageBoolean(KEY, true));
    expect(result.current[0]).toBe(false);
  });

  it("toggle flips the value and persists it", () => {
    const { result } = renderHook(() => useLocalStorageBoolean(KEY, true));
    act(() => result.current[1]());
    expect(result.current[0]).toBe(false);
    expect(localStorage.getItem(KEY)).toBe("false");
    act(() => result.current[1]());
    expect(result.current[0]).toBe(true);
    expect(localStorage.getItem(KEY)).toBe("true");
  });

  it("falls back to the default when the stored value is malformed", () => {
    localStorage.setItem(KEY, "not-a-boolean");
    const { result } = renderHook(() => useLocalStorageBoolean(KEY, true));
    expect(result.current[0]).toBe(true);
  });
});
