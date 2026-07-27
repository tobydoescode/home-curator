import { Alert, Stack, Text, Title } from "@mantine/core";
import { useDebouncedValue } from "@mantine/hooks";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { RowSelectionState } from "@tanstack/react-table";

import { ColumnVisibilityGear } from "@/components/ColumnVisibility/ColumnVisibilityGear";
import { useColumnVisibility } from "@/components/ColumnVisibility/useColumnVisibility";
import { PaginationFooter } from "@/components/PaginationFooter";
import { SEARCH_DEBOUNCE_MS } from "@/constants";
import { useDevices, type DevicesSortBy } from "@/hooks/useDevices";
import { useTableUrlState } from "@/hooks/useTableUrlState";
import { ActionRow } from "./ActionRow";
import { DevicesTable, type DeviceRow } from "./DevicesTable";
import { FilterBar, type Filters } from "./FilterBar";
import { EditDeviceDrawer } from "./EditDeviceDrawer";

// Every column id rendered by `DevicesTable`, in the order shown to users.
// Keep in sync with `DevicesTable`'s column defs. `select` and `link` are
// fixed (no user-controlled visibility) so they're omitted from the gear.
const DEVICES_COLUMNS: { id: string; label: string }[] = [
  { id: "severity", label: "Severity" },
  { id: "name", label: "Device Name" },
  { id: "room", label: "Room" },
  { id: "integration", label: "Integration" },
  { id: "created", label: "Created" },
  { id: "modified", label: "Modified" },
];

const DEVICES_COLUMN_IDS = DEVICES_COLUMNS.map((c) => c.id);
const DEVICES_DEFAULT_VISIBLE = DEVICES_COLUMN_IDS;  // all visible (no regression)

// Filter field → repeated query parameter. They differ: `rooms` is `?room=`.
const DEVICES_ARRAY_FILTERS = {
  rooms: "room",
  issue_types: "issue_type",
  integrations: "integration",
} as const;
const DEVICES_BOOLEAN_FILTERS = ["with_issues"] as const;

export function DevicesPage() {
  const [selection, setSelection] = useState<RowSelectionState>({});
  const [params, setParams] = useSearchParams();
  const {
    filters,
    page,
    pageSize,
    sortBy,
    sortDir,
    setFilters,
    setPage,
    setPageSize,
    cycleSort,
  } = useTableUrlState<Filters, DevicesSortBy>({
    arrays: DEVICES_ARRAY_FILTERS,
    booleans: DEVICES_BOOLEAN_FILTERS,
  });

  // Derived from the URL rather than local state, matching EntitiesPage:
  // one source of truth, and it makes /devices?device=<id> deep-linkable.
  const drawerId = params.get("device");

  function openDrawer(id: string): void {
    const next = new URLSearchParams(params);
    next.set("device", id);
    setParams(next, { replace: true });
  }

  function closeDrawer(): void {
    const next = new URLSearchParams(params);
    next.delete("device");
    setParams(next, { replace: true });
  }

  const columnVis = useColumnVisibility({
    storageKey: "home-curator:columns:devices",
    allColumns: DEVICES_COLUMN_IDS,
    defaultVisible: DEVICES_DEFAULT_VISIBLE,
  });


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
    if (drawerId !== null && data && !active) closeDrawer();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [drawerId, data, active]);

  // Prune selection down to what is actually on screen. Without this, acting
  // on a selection after filtering operates on rows the user can no longer
  // see, and the counter disagrees with the table. EntitiesPage already did
  // this; Devices did not.
  useEffect(() => {
    if (!data) return;
    const visible = new Set(data.devices.map((d) => d.id));
    let changed = false;
    const next: RowSelectionState = {};
    for (const id of Object.keys(selection)) {
      if (visible.has(id)) {
        next[id] = selection[id];
      } else {
        changed = true;
      }
    }
    if (changed) setSelection(next);
  }, [data, selection]);

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
        onChange={setFilters}
        rightSlot={
          <ColumnVisibilityGear
            columns={DEVICES_COLUMNS}
            visible={columnVis.visible}
            onToggle={columnVis.toggle}
            onReset={columnVis.reset}
          />
        }
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
        onRowClick={openDrawer}
        sortBy={sortBy}
        sortDir={sortDir}
        onSort={cycleSort}
        columnVisibility={columnVis.visible}
      />
      <PaginationFooter
        total={data.total}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        onPageSizeChange={setPageSize}
      />
      <EditDeviceDrawer
        opened={drawerId !== null}
        onClose={closeDrawer}
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
