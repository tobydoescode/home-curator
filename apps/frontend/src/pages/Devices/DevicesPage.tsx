import { Alert, Stack, Text, Title } from "@mantine/core";
import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { RowSelectionState } from "@tanstack/react-table";

import { useDevices } from "@/hooks/useDevices";
import { DevicesTable } from "./DevicesTable";
import { FilterBar, type Filters } from "./FilterBar";
import { PaginationFooter } from "./PaginationFooter";

function filtersFromParams(p: URLSearchParams): Filters {
  return {
    q: p.get("q") ?? "",
    regex: p.get("regex") === "true",
    room: p.get("room"),
    issue_type: p.get("issue_type"),
    with_issues: p.get("with_issues") === "true",
  };
}

function paramsFromFiltersAndPagination(
  f: Filters,
  page: number,
  pageSize: number,
): Record<string, string> {
  const out: Record<string, string> = {};
  if (f.q) out.q = f.q;
  if (f.regex) out.regex = "true";
  if (f.room) out.room = f.room;
  if (f.issue_type) out.issue_type = f.issue_type;
  if (f.with_issues) out.with_issues = "true";
  if (page !== 1) out.page = String(page);
  if (pageSize !== 50) out.page_size = String(pageSize);
  return out;
}

export function DevicesPage() {
  const [selection, setSelection] = useState<RowSelectionState>({});
  const [params, setParams] = useSearchParams();

  const filters = useMemo(() => filtersFromParams(params), [params]);
  const page = Number(params.get("page") ?? 1);
  const pageSize = Number(params.get("page_size") ?? 50);

  const { data, isLoading, error } = useDevices({
    q: filters.q || undefined,
    regex: filters.regex || undefined,
    room: filters.room ?? undefined,
    issue_type: filters.issue_type ?? undefined,
    with_issues: filters.with_issues || undefined,
    page,
    page_size: pageSize,
  });

  const rooms = useMemo(
    () =>
      Array.from(
        new Set(
          (data?.devices.map((d) => d.area_name).filter(Boolean) as string[]) ??
            [],
        ),
      ),
    [data],
  );
  const issueTypes = useMemo(
    () => Object.keys(data?.issue_counts_by_type ?? {}),
    [data],
  );

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
        with issues
      </Text>
      <FilterBar
        filters={filters}
        rooms={rooms}
        issueTypes={issueTypes}
        onChange={(f) => setParams(paramsFromFiltersAndPagination(f, 1, pageSize))}
      />
      <DevicesTable
        rows={data.devices.map((d) => ({
          id: d.id,
          name: d.name,
          area_name: d.area_name ?? null,
          issue_count: d.issue_count,
          highest_severity: d.highest_severity ?? null,
        }))}
        selection={selection}
        onSelectionChange={setSelection}
      />
      <PaginationFooter
        total={data.total}
        page={page}
        pageSize={pageSize}
        onPageChange={(p) =>
          setParams(paramsFromFiltersAndPagination(filters, p, pageSize))
        }
        onPageSizeChange={(s) =>
          setParams(paramsFromFiltersAndPagination(filters, 1, s))
        }
      />
    </Stack>
  );
}
