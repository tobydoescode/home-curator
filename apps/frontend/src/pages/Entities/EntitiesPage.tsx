import { Alert, Stack, Text, Title } from "@mantine/core";
import { useDebouncedValue } from "@mantine/hooks";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { RowSelectionState } from "@tanstack/react-table";

import { ColumnVisibilityGear } from "@/components/ColumnVisibility/ColumnVisibilityGear";
import { useColumnVisibility } from "@/components/ColumnVisibility/useColumnVisibility";
import { SEARCH_DEBOUNCE_MS } from "@/constants";
import {
  type EntitiesSortBy,
  type EntitiesSortDir,
  useEntities,
} from "@/hooks/useEntities";

import { ActionRow } from "./ActionRow";
import { EditEntityDrawer } from "./EditEntityDrawer";
import { EntitiesTable, type EntityRow } from "./EntitiesTable";
import { FilterBar, type Filters } from "./FilterBar";
import { PaginationFooter } from "./PaginationFooter";

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
const ENTITIES_DEFAULT_VISIBLE = [
  "severity",
  "entity_id",
  "name",
  "domain",
  "room",
  "device",
  "issues",
];

function filtersFromParams(p: URLSearchParams): Filters {
  return {
    q: p.get("q") ?? "",
    regex: p.get("regex") === "true",
    domains: p.getAll("domain"),
    rooms: p.getAll("room"),
    integrations: p.getAll("integration"),
    issue_types: p.getAll("issue_type"),
    with_issues: p.get("with_issues") === "true",
    show_disabled: p.get("show_disabled") === "true",
    show_hidden: p.get("show_hidden") === "true",
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
  for (const d of f.domains) out.append("domain", d);
  for (const r of f.rooms) out.append("room", r);
  for (const i of f.integrations) out.append("integration", i);
  for (const t of f.issue_types) out.append("issue_type", t);
  if (f.with_issues) out.set("with_issues", "true");
  if (f.show_disabled) out.set("show_disabled", "true");
  if (f.show_hidden) out.set("show_hidden", "true");
  if (page !== 1) out.set("page", String(page));
  if (pageSize !== 50) out.set("page_size", String(pageSize));
  if (current) {
    for (const key of ["sort_by", "sort_dir"]) {
      const v = current.get(key);
      if (v) out.set(key, v);
    }
  }
  return out;
}

export function EntitiesPage() {
  const [selection, setSelection] = useState<RowSelectionState>({});
  const [drawerEntityId, setDrawerEntityId] = useState<string | null>(null);
  const [params, setParams] = useSearchParams();

  // Deep-link support: /entities?entity=<id> opens the drawer on mount and
  // keeps the URL in sync with the drawer state while the page is open.
  useEffect(() => {
    const q = params.get("entity");
    if (q && q !== drawerEntityId) setDrawerEntityId(q);
  }, [params, drawerEntityId]);

  useEffect(() => {
    const current = params.get("entity");
    if (drawerEntityId && current !== drawerEntityId) {
      const next = new URLSearchParams(params);
      next.set("entity", drawerEntityId);
      setParams(next, { replace: true });
    } else if (!drawerEntityId && current) {
      const next = new URLSearchParams(params);
      next.delete("entity");
      setParams(next, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [drawerEntityId]);

  const filters = useMemo(() => filtersFromParams(params), [params]);
  const page = Number(params.get("page") ?? 1);
  const pageSize = Number(params.get("page_size") ?? 50);
  const sortBy = (params.get("sort_by") as EntitiesSortBy | null) || null;
  const sortDir: EntitiesSortDir =
    params.get("sort_dir") === "desc" ? "desc" : "asc";

  function cycleSort(column: EntitiesSortBy) {
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
        onChange={(f) =>
          setParams(paramsFromFiltersAndPagination(f, 1, pageSize, params))
        }
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
        onRowClick={setDrawerEntityId}
        sortBy={sortBy}
        sortDir={sortDir}
        onSort={cycleSort}
        columnVisibility={columnVis.visible}
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
      <EditEntityDrawer
        opened={drawerEntityId !== null}
        onClose={() => setDrawerEntityId(null)}
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
