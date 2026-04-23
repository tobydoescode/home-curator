import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { useColumnVisibility } from "./useColumnVisibility";

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  window.localStorage.clear();
});

describe("useColumnVisibility", () => {
  it("returns the default-visible set on first load", () => {
    const { result } = renderHook(() =>
      useColumnVisibility({
        storageKey: "test:cols:a",
        allColumns: ["name", "room", "extra"],
        defaultVisible: ["name", "room"],
      }),
    );
    expect(result.current.isVisible("name")).toBe(true);
    expect(result.current.isVisible("room")).toBe(true);
    expect(result.current.isVisible("extra")).toBe(false);
  });

  it("toggle() flips a single column and persists to localStorage", () => {
    const { result, rerender } = renderHook(() =>
      useColumnVisibility({
        storageKey: "test:cols:b",
        allColumns: ["a", "b"],
        defaultVisible: ["a", "b"],
      }),
    );
    act(() => result.current.toggle("b"));
    expect(result.current.isVisible("b")).toBe(false);
    expect(window.localStorage.getItem("test:cols:b")).not.toBeNull();

    // Re-mount with same key — state must rehydrate.
    rerender();
    const { result: result2 } = renderHook(() =>
      useColumnVisibility({
        storageKey: "test:cols:b",
        allColumns: ["a", "b"],
        defaultVisible: ["a", "b"],
      }),
    );
    expect(result2.current.isVisible("b")).toBe(false);
  });

  it("reset() restores defaults and clears storage", () => {
    const { result } = renderHook(() =>
      useColumnVisibility({
        storageKey: "test:cols:c",
        allColumns: ["a", "b"],
        defaultVisible: ["a"],
      }),
    );
    act(() => result.current.toggle("b"));
    expect(result.current.isVisible("b")).toBe(true);
    act(() => result.current.reset());
    expect(result.current.isVisible("b")).toBe(false);
    expect(result.current.isVisible("a")).toBe(true);
    expect(window.localStorage.getItem("test:cols:c")).toBeNull();
  });

  it("scoped keys isolate devices from entities", () => {
    const { result: a } = renderHook(() =>
      useColumnVisibility({
        storageKey: "home-curator:columns:devices",
        allColumns: ["name", "room"],
        defaultVisible: ["name", "room"],
      }),
    );
    act(() => a.current.toggle("room"));

    const { result: b } = renderHook(() =>
      useColumnVisibility({
        storageKey: "home-curator:columns:entities",
        allColumns: ["entity_id", "room"],
        defaultVisible: ["entity_id", "room"],
      }),
    );
    expect(b.current.isVisible("room")).toBe(true);
    expect(a.current.isVisible("room")).toBe(false);
  });

  it("returns a TanStack-shaped `visible` map covering every known column", () => {
    const { result } = renderHook(() =>
      useColumnVisibility({
        storageKey: "test:cols:d",
        allColumns: ["a", "b", "c"],
        defaultVisible: ["a"],
      }),
    );
    expect(result.current.visible).toEqual({ a: true, b: false, c: false });
  });
});
