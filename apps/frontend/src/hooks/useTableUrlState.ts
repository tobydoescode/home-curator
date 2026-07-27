import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";

/**
 * URL-backed filter, pagination and sort state for a listing page.
 *
 * The Devices and Entities pages each had their own copy of this — the same
 * `filtersFromParams`, `paramsFromFiltersAndPagination` and `cycleSort`,
 * differing only in which keys they knew about. Keeping the URL as the single
 * source of truth means filters survive a refresh and are shareable; keeping
 * *one* implementation of it means the two pages cannot quietly disagree about
 * what a filter change does to the page number, or which params survive a
 * sort. They already had: only one of the two pruned selection when rows left
 * the result set.
 *
 * Field names and query parameters are not always the same — a `rooms` field
 * is a repeated `room` parameter — so arrays are declared as a mapping rather
 * than a list of keys.
 */

export type SortDir = "asc" | "desc";

export interface BaseFilters {
  q: string;
  regex: boolean;
}

interface Config {
  /** Filter field name → repeated query parameter name. */
  arrays: Readonly<Record<string, string>>;
  /** Boolean filter fields, serialised as `?key=true` and absent when false. */
  booleans: readonly string[];
  defaultPageSize?: number;
}

export interface TableUrlState<F extends BaseFilters, S extends string> {
  filters: F;
  page: number;
  pageSize: number;
  sortBy: S | null;
  sortDir: SortDir;
  /** Applying a filter always returns to page 1; the old page may not exist. */
  setFilters: (next: F) => void;
  setPage: (page: number) => void;
  setPageSize: (size: number) => void;
  /** Ascending → descending → unsorted, resetting to page 1. */
  cycleSort: (column: S) => void;
}

export function useTableUrlState<F extends BaseFilters, S extends string>({
  arrays,
  booleans,
  defaultPageSize = 50,
}: Config): TableUrlState<F, S> {
  const [params, setParams] = useSearchParams();

  const filters = useMemo(() => {
    const out: Record<string, unknown> = {
      q: params.get("q") ?? "",
      regex: params.get("regex") === "true",
    };
    for (const [field, param] of Object.entries(arrays)) {
      out[field] = params.getAll(param);
    }
    for (const field of booleans) {
      out[field] = params.get(field) === "true";
    }
    return out as F;
    // `arrays` and `booleans` are module-level constants at every call site.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params]);

  const page = Number(params.get("page") ?? 1);
  const pageSize = Number(params.get("page_size") ?? defaultPageSize);
  const sortBy = (params.get("sort_by") as S | null) || null;
  const sortDir: SortDir = params.get("sort_dir") === "desc" ? "desc" : "asc";

  const write = useCallback(
    (next: F, nextPage: number, nextPageSize: number) => {
      const out = new URLSearchParams();
      if (next.q) out.set("q", next.q);
      if (next.regex) out.set("regex", "true");
      // `F` is a concrete interface at each call site, so it has no index
      // signature; read it as an untyped record for the generic walk.
      const values = next as unknown as Record<string, unknown>;
      for (const [field, param] of Object.entries(arrays)) {
        for (const value of (values[field] as string[] | undefined) ?? []) {
          out.append(param, value);
        }
      }
      for (const field of booleans) {
        if (values[field]) out.set(field, "true");
      }
      if (nextPage !== 1) out.set("page", String(nextPage));
      if (nextPageSize !== defaultPageSize) {
        out.set("page_size", String(nextPageSize));
      }
      // Sort is orthogonal to filtering, so a filter change must not discard
      // the user's chosen column.
      for (const key of ["sort_by", "sort_dir"]) {
        const value = params.get(key);
        if (value) out.set(key, value);
      }
      // Anything else already on the URL — an open drawer, say — is dropped
      // deliberately: it refers to a row that may not survive the new filter.
      setParams(out);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [params, setParams, defaultPageSize],
  );

  const cycleSort = useCallback(
    (column: S) => {
      const next = new URLSearchParams(params);
      if (sortBy !== column) {
        next.set("sort_by", column);
        next.set("sort_dir", "asc");
      } else if (sortDir === "asc") {
        next.set("sort_dir", "desc");
      } else {
        next.delete("sort_by");
        next.delete("sort_dir");
      }
      next.set("page", "1");
      setParams(next);
    },
    [params, setParams, sortBy, sortDir],
  );

  return {
    filters,
    page,
    pageSize,
    sortBy,
    sortDir,
    setFilters: (next) => write(next, 1, pageSize),
    setPage: (next) => write(filters, next, pageSize),
    setPageSize: (size) => write(filters, 1, size),
    cycleSort,
  };
}
