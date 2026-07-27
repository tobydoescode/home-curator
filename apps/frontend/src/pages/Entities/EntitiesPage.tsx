import { Alert, Stack, Text, Title } from "@mantine/core";
import { useDebouncedValue } from "@mantine/hooks";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { RowSelectionState } from "@tanstack/react-table";

import { ColumnVisibilityGear } from "@/components/ColumnVisibility/ColumnVisibilityGear";
import { useColumnVisibility } from "@/components/ColumnVisibility/useColumnVisibility";
import { PaginationFooter } from "@/components/PaginationFooter";
import { SEARCH_DEBOUNCE_MS } from "@/constants";
import { type EntitiesSortBy, useEntities } from "@/hooks/useEntities";
import { useTableUrlState } from "@/hooks/useTableUrlState";

import { ActionRow } from "./ActionRow";
import { EditEntityDrawer } from "./EditEntityDrawer";
import { EntitiesTable, type EntityRow } from "./EntitiesTable";
import { FilterBar, type Filters } from "./FilterBar";

const ENTITIES_COLUMNS: { id: string; label: string }[] = [
  { id: "severity", label: "Severity" },
  { id: "entity_id", label: "Entity ID" },
  { id: "name", label: "Name" },
  { id: "domain", label: "Domain" },
  { id: "room", label: "Room" },
  { id: "device", label: "Device" },
  { id: "issues", label: "Issues" },
  { id: "integration", label: "Integration" },
  { id: "disabled", label: "Disabled" },
  { id: "hidden", label: "Hidden" },
  { id: "created", label: "Created" },
  { id: "modified", label: "Modified" },
];

const ENTITIES_COLUMN_IDS = ENTITIES_COLUMNS.map((c) => c.id);
// Filter field → repeated query parameter; they differ (`rooms` is `?room=`).
const ENTITIES_ARRAY_FILTERS = {
  domains: "domain",
  rooms: "room",
  integrations: "integration",
  issue_types: "issue_type",
} as const;
const ENTITIES_BOOLEAN_FILTERS = [
  "with_issues",
  "show_disabled",
  "show_hidden",
] as const;

const ENTITIES_DEFAULT_VISIBLE = [
  "severity",
  "entity_id",
  "name",
  "domain",
  "room",
  "device",
  "issues",
];

export function EntitiesPage() {
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
  } = useTableUrlState<Filters, EntitiesSortBy>({
    arrays: ENTITIES_ARRAY_FILTERS,
    booleans: ENTITIES_BOOLEAN_FILTERS,
  });

  // The drawer's open state is derived from the URL — no local state. Two
  // effects syncing URL↔state caused a race: when Close cleared the state,
  // the URL→state effect ran before the state→URL effect cleared the param,
  // immediately reopening the drawer. Single source of truth (URL) avoids
  // the loop and still supports deep-links from /entities?entity=<id>.
  const drawerEntityId = params.get("entity");

  function openDrawer(id: string): void {
    const next = new URLSearchParams(params);
    next.set("entity", id);
    setParams(next, { replace: true });
  }

  function closeDrawer(): void {
    const next = new URLSearchParams(params);
    next.delete("entity");
    setParams(next, { replace: true });
  }


  const [debouncedQ] = useDebouncedValue(filters.q, SEARCH_DEBOUNCE_MS);

  const { data, isLoading, error } = useEntities({
    q: debouncedQ || undefined,
    regex: filters.regex || undefined,
    domain: filters.domains.length ? filters.domains : undefined,
    room: filters.rooms.length ? filters.rooms : undefined,
    integration: filters.integrations.length ? filters.integrations : undefined,
    issue_type: filters.issue_types.length ? filters.issue_types : undefined,
    with_issues: filters.with_issues || undefined,
    show_disabled: filters.show_disabled || undefined,
    show_hidden: filters.show_hidden || undefined,
    page,
    page_size: pageSize,
    sort_by: sortBy ?? undefined,
    sort_dir: sortBy ? sortDir : undefined,
  });

  const domains = useMemo(() => data?.all_domains ?? [], [data]);
  const rooms = useMemo(
    () => (data?.all_areas ?? []).map((a) => a.name),
    [data],
  );
  const roomsForAssign = useMemo(
    () => (data?.all_areas ?? []).map((a) => ({ id: a.id, name: a.name })),
    [data],
  );
  const integrations = useMemo(() => data?.all_integrations ?? [], [data]);
  const issueTypes = useMemo(() => data?.all_issue_types ?? [], [data]);

  const entityRows: EntityRow[] = useMemo(
    () =>
      data?.entities.map((e) => ({
        entity_id: e.entity_id,
        name: e.name ?? null,
        original_name: e.original_name ?? null,
        display_name: e.display_name,
        domain: e.domain,
        platform: e.platform ?? null,
        device_id: e.device_id ?? null,
        device_name: e.device_name ?? null,
        area_id: e.area_id ?? null,
        area_name: e.area_name ?? null,
        disabled_by: e.disabled_by ?? null,
        hidden_by: e.hidden_by ?? null,
        created_at: e.created_at ?? null,
        modified_at: e.modified_at ?? null,
        issue_count: e.issue_count,
        highest_severity: e.highest_severity ?? null,
      })) ?? [],
    [data],
  );

  const selectedIds = useMemo(
    () => Object.keys(selection).filter((k) => selection[k]),
    [selection],
  );

  const columnVis = useColumnVisibility({
    storageKey: "home-curator:columns:entities",
    allColumns: ENTITIES_COLUMN_IDS,
    defaultVisible: ENTITIES_DEFAULT_VISIBLE,
  });

  // Prune stale selection when filters/pagination drop those entities from
  // the page. Otherwise the selection counter desyncs from what's visible.
  useEffect(() => {
    if (!data) return;
    const visible = new Set(data.entities.map((e) => e.entity_id));
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
      <Alert color="red" title="Failed To Load Entities">
        {String(error)}
      </Alert>
    );
  if (!data) return null;

  const issueTotal = Object.values(data.issue_counts_by_type ?? {}).reduce(
    (a, b) => a + b,
    0,
  );

  return (
    <Stack gap="md">
      <Title order={3}>Entities</Title>
      <Text c="dimmed" size="sm">
        {data.total} entities · {issueTotal} issues
      </Text>
      <FilterBar
        filters={filters}
        domains={domains}
        rooms={rooms}
        integrations={integrations}
        issueTypes={issueTypes}
        domainCounts={data.domain_counts}
        roomCounts={data.area_counts}
        integrationCounts={data.integration_counts}
        issueTypeCounts={data.issue_counts_by_type}
        onChange={setFilters}
        rightSlot={
          <ColumnVisibilityGear
            columns={ENTITIES_COLUMNS}
            visible={columnVis.visible}
            onToggle={columnVis.toggle}
            onReset={columnVis.reset}
          />
        }
      />
      <ActionRow
        selectedIds={selectedIds}
        rooms={roomsForAssign}
        onClearSelection={() => setSelection({})}
      />
      <EntitiesTable
        rows={entityRows}
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
      <EditEntityDrawer
        opened={drawerEntityId !== null}
        onClose={closeDrawer}
        entity={
          drawerEntityId
            ? (() => {
                const e = data.entities.find(
                  (x) => x.entity_id === drawerEntityId,
                );
                if (!e) return null;
                return {
                  entity_id: e.entity_id,
                  name: e.name ?? null,
                  original_name: e.original_name ?? null,
                  domain: e.domain,
                  platform: e.platform ?? "",
                  device_id: e.device_id ?? null,
                  device_name: e.device_name ?? null,
                  area_id: e.area_id ?? null,
                  area_name: e.area_name ?? null,
                  disabled_by: e.disabled_by ?? null,
                  hidden_by: e.hidden_by ?? null,
                  icon: e.icon ?? null,
                  issues: e.issues ?? [],
                };
              })()
            : null
        }
        areas={roomsForAssign}
      />
    </Stack>
  );
}
