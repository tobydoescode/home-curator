import { act, renderHook } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { useTableUrlState, type BaseFilters } from "./useTableUrlState";

interface Filters extends BaseFilters {
  rooms: string[];
  issue_types: string[];
  with_issues: boolean;
}

const ARRAYS = { rooms: "room", issue_types: "issue_type" } as const;
const BOOLEANS = ["with_issues"] as const;

type Sort = "name" | "room";

function setup(initialUrl = "/devices") {
  const wrapper = ({ children }: { children: ReactNode }) =>
    createElement(MemoryRouter, { initialEntries: [initialUrl] }, children);
  return renderHook(
    () =>
      useTableUrlState<Filters, Sort>({ arrays: ARRAYS, booleans: BOOLEANS }),
    { wrapper },
  );
}

describe("useTableUrlState", () => {
  it("defaults to empty filters on a bare URL", () => {
    const { result } = setup();

    expect(result.current.filters).toEqual({
      q: "",
      regex: false,
      rooms: [],
      issue_types: [],
      with_issues: false,
    });
    expect(result.current.page).toBe(1);
    expect(result.current.pageSize).toBe(50);
    expect(result.current.sortBy).toBeNull();
  });

  it("reads filters out of the URL, mapping fields to their parameters", () => {
    // `rooms` is a repeated `room` parameter — the names differ.
    const { result } = setup(
      "/devices?q=lamp&regex=true&room=Kitchen&room=Hall&issue_type=missing_area&with_issues=true",
    );

    expect(result.current.filters).toEqual({
      q: "lamp",
      regex: true,
      rooms: ["Kitchen", "Hall"],
      issue_types: ["missing_area"],
      with_issues: true,
    });
  });

  it("round-trips filters back onto the URL", () => {
    const { result } = setup();

    act(() =>
      result.current.setFilters({
        q: "lamp",
        regex: false,
        rooms: ["Kitchen", "Hall"],
        issue_types: [],
        with_issues: true,
      }),
    );

    expect(result.current.filters.rooms).toEqual(["Kitchen", "Hall"]);
    expect(result.current.filters.with_issues).toBe(true);
    // False booleans and empty arrays stay off the URL rather than being
    // serialised as noise.
    expect(result.current.filters.regex).toBe(false);
    expect(result.current.filters.issue_types).toEqual([]);
  });

  it("returns to page 1 when filters change", () => {
    // The old page may not exist under the new filter.
    const { result } = setup("/devices?page=3");
    expect(result.current.page).toBe(3);

    act(() =>
      result.current.setFilters({
        q: "x",
        regex: false,
        rooms: [],
        issue_types: [],
        with_issues: false,
      }),
    );

    expect(result.current.page).toBe(1);
  });

  it("keeps the chosen sort when filters change", () => {
    // Sort is orthogonal to filtering; changing one must not discard the other.
    const { result } = setup("/devices?sort_by=room&sort_dir=desc");

    act(() =>
      result.current.setFilters({
        q: "x",
        regex: false,
        rooms: [],
        issue_types: [],
        with_issues: false,
      }),
    );

    expect(result.current.sortBy).toBe("room");
    expect(result.current.sortDir).toBe("desc");
  });

  it("cycles a column ascending, descending, then off", () => {
    const { result } = setup();

    act(() => result.current.cycleSort("name"));
    expect([result.current.sortBy, result.current.sortDir]).toEqual([
      "name",
      "asc",
    ]);

    act(() => result.current.cycleSort("name"));
    expect(result.current.sortDir).toBe("desc");

    act(() => result.current.cycleSort("name"));
    expect(result.current.sortBy).toBeNull();
  });

  it("starts a different column ascending rather than inheriting a direction", () => {
    const { result } = setup("/devices?sort_by=name&sort_dir=desc");

    act(() => result.current.cycleSort("room"));

    expect([result.current.sortBy, result.current.sortDir]).toEqual([
      "room",
      "asc",
    ]);
  });

  it("resets to page 1 when the sort changes", () => {
    const { result } = setup("/devices?page=4");

    act(() => result.current.cycleSort("name"));

    expect(result.current.page).toBe(1);
  });

  it("preserves filters when paging", () => {
    const { result } = setup("/devices?room=Kitchen&with_issues=true");

    act(() => result.current.setPage(2));

    expect(result.current.page).toBe(2);
    expect(result.current.filters.rooms).toEqual(["Kitchen"]);
    expect(result.current.filters.with_issues).toBe(true);
  });

  it("returns to page 1 when the page size changes", () => {
    const { result } = setup("/devices?page=5");

    act(() => result.current.setPageSize(100));

    expect(result.current.pageSize).toBe(100);
    expect(result.current.page).toBe(1);
  });
});
