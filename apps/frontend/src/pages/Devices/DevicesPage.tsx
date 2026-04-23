import { Alert, Stack, Text, Title } from "@mantine/core";
import { useDebouncedValue } from "@mantine/hooks";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { RowSelectionState } from "@tanstack/react-table";

import { SEARCH_DEBOUNCE_MS } from "@/constants";
import { useDevices, type DevicesSortBy, type DevicesSortDir } from "@/hooks/useDevices";
import { ActionRow } from "./ActionRow";
import { DevicesTable, type DeviceRow } from "./DevicesTable";
import { FilterBar, type Filters } from "./FilterBar";
import { EditDeviceDrawer } from "./EditDeviceDrawer";
import { PaginationFooter } from "./PaginationFooter";

function filtersFromParams(p: URLSearchParams): Filters {
  return {
    q: p.get("q") ?? "",
    regex: p.get("regex") === "true",
    rooms: p.getAll("room"),
    issue_types: p.getAll("issue_type"),
    integrations: p.getAll("integration"),
    with_issues: p.get("with_issues") === "true",
  };
}

function paramsFromFiltersAndPagination(
  f: Filters,
  page: number,
  pageSize: number,
  current?: URLSearchParams,
): URLSearchParams {
  const out = new URLSearchParams();
  if (f.q) out.set("q", f.q);
  if (f.regex) out.set("regex", "true");
  for (const r of f.rooms) out.append("room", r);
  for (const t of f.issue_types) out.append("issue_type", t);
  for (const i of f.integrations) out.append("integration", i);
  if (f.with_issues) out.set("with_issues", "true");
  if (page !== 1) out.set("page", String(page));
  if (pageSize !== 50) out.set("page_size", String(pageSize));
  // Preserve orthogonal params (sort) so a filter change doesn't wipe
  // the user's chosen column ordering.
  if (current) {
    for (const key of ["sort_by", "sort_dir"]) {
      const v = current.get(key);
      if (v) out.set(key, v);
    }
  }
  return out;
}

export function DevicesPage() {
  const [selection, setSelection] = useState<RowSelectionState>({});
  const [drawerId, setDrawerId] = useState<string | null>(null);
  const [params, setParams] = useSearchParams();

  const filters = useMemo(() => filtersFromParams(params), [params]);
  const page = Number(params.get("page") ?? 1);
  const pageSize = Number(params.get("page_size") ?? 50);
  const sortBy = (params.get("sort_by") as DevicesSortBy | null) || null;
  const sortDir: DevicesSortDir = params.get("sort_dir") === "desc" ? "desc" : "asc";

  function cycleSort(column: DevicesSortBy) {
    const next = new URLSearchParams(params);
    if (sortBy !== column) {
      // First click on a new column → ascending.
      next.set("sort_by", column);
      next.set("sort_dir", "asc");
    } else if (sortDir === "asc") {
      // Second click → flip to descending.
      next.set("sort_dir", "desc");
    } else {
      // Third click → clear the sort.
      next.delete("sort_by");
      next.delete("sort_dir");
    }
    next.set("page", "1");  // any sort change resets to page 1
    setParams(next);
  }

  // Debounce only the free-text search — dropdowns/toggles fire immediately
  // because they're already discrete clicks.
  const [debouncedQ] = useDebouncedValue(filters.q, SEARCH_DEBOUNCE_MS);

  const { data, isLoading, error } = useDevices({
    q: debouncedQ || undefined,
    regex: filters.regex || undefined,
    room: filters.rooms.length ? filters.rooms : undefined,
    issue_type: filters.issue_types.length ? filters.issue_types : undefined,
    integration: filters.integrations.length ? filters.integrations : undefined,
    with_issues: filters.with_issues || undefined,
    page,
    page_size: pageSize,
    sort_by: sortBy ?? undefined,
    sort_dir: sortBy ? sortDir : undefined,
  });

  // Dropdown options come from the full universe (all_areas / all_issue_types)
  // so filters don't shrink their own option lists as you select values.
  const rooms = useMemo(
    () => (data?.all_areas ?? []).map((a) => a.name),
    [data],
  );

  const roomsForAssign = useMemo(
    () => (data?.all_areas ?? []).map((a) => ({ id: a.id, name: a.name })),
    [data],
  );

  const issueTypes = useMemo(() => data?.all_issue_types ?? [], [data]);

  const integrations = useMemo(() => data?.all_integrations ?? [], [data]);

  const deviceRows: DeviceRow[] = useMemo(
    () =>
      data?.devices.map((d) => ({
        id: d.id,
        name: d.name,
        area_name: d.area_name ?? null,
        integration: d.integration ?? null,
        created_at: d.created_at ?? null,
        modified_at: d.modified_at ?? null,
        issue_count: d.issue_count,
        highest_severity: d.highest_severity ?? null,
      })) ?? [],
    [data],
  );

  const deviceLookup = useMemo(() => {
    const m: Record<string, DeviceRow> = {};
    for (const r of deviceRows) m[r.id] = r;
    return m;
  }, [deviceRows]);

  const selectedIds = useMemo(
    () => Object.keys(selection).filter((k) => selection[k]),
    [selection],
  );

  const active = useMemo(
    () => data?.devices.find((d) => d.id === drawerId) ?? null,
    [data, drawerId],
  );

  // If the currently-drawered device disappears from the result set (e.g.
  // deleted via HA → SSE → refetch), close the drawer so it doesn't
  // "teleport" back if the device reappears later.
  useEffect(() => {
    if (drawerId !== null && data && !active) setDrawerId(null);
  }, [drawerId, data, active]);

  if (isLoading) return <Text>Loading…</Text>;
  if (error)
    return (
      <Alert color="red" title="Failed To Load Devices">
        {String(error)}
      </Alert>
    );
  if (!data) return null;

  return (
    <Stack gap="md">
      <Title order={3}>Devices</Title>
      <Text c="dimmed" size="sm">
        {data.total} devices ·{" "}
        {Object.values(data.issue_counts_by_type).reduce((a, b) => a + b, 0)}{" "}
        issues
      </Text>
      <FilterBar
        filters={filters}
        rooms={rooms}
        issueTypes={issueTypes}
        integrations={integrations}
        roomCounts={data.area_counts}
        issueTypeCounts={data.issue_counts_by_type}
        integrationCounts={data.integration_counts}
        onChange={(f) => setParams(paramsFromFiltersAndPagination(f, 1, pageSize, params))}
      />
      <ActionRow
        selectedIds={selectedIds}
        rooms={roomsForAssign}
        deviceLookup={deviceLookup}
        onClearSelection={() => setSelection({})}
      />
      <DevicesTable
        rows={deviceRows}
        selection={selection}
        onSelectionChange={setSelection}
        onRowClick={setDrawerId}
        sortBy={sortBy}
        sortDir={sortDir}
        onSort={cycleSort}
      />
      <PaginationFooter
        total={data.total}
        page={page}
        pageSize={pageSize}
        onPageChange={(p) =>
          setParams(paramsFromFiltersAndPagination(filters, p, pageSize, params))
        }
        onPageSizeChange={(s) =>
          setParams(paramsFromFiltersAndPagination(filters, 1, s, params))
        }
      />
      <EditDeviceDrawer
        opened={drawerId !== null}
        onClose={() => setDrawerId(null)}
        device={
          active
            ? {
                id: active.id,
                name: active.name,
                name_by_user: active.name_by_user ?? null,
                area_id: active.area_id ?? null,
                area_name: active.area_name ?? null,
                issues: active.issues ?? [],
              }
            : null
        }
        areas={roomsForAssign}
      />
    </Stack>
  );
}
