import { ActionIcon, Checkbox, Group, Table, Tooltip, UnstyledButton } from "@mantine/core";
import {
  IconChevronDown,
  IconChevronUp,
  IconExternalLink,
  IconSelector,
} from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import {
  type ColumnDef,
  type OnChangeFn,
  type RowSelectionState,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";

import { SeverityBadge } from "@/components/SeverityBadge";
import type { DevicesSortBy, DevicesSortDir } from "@/hooks/useDevices";

export interface DeviceRow {
  id: string;
  name: string;
  area_name: string | null;
  integration: string | null;
  created_at: string | null;
  modified_at: string | null;
  issue_count: number;
  highest_severity: "info" | "warning" | "error" | null;
}

/** Render an ISO-8601 timestamp as a short "YYYY-MM-DD" for dense tables. */
function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  // Trust the backend-provided ISO string; slice to the date portion to keep
  // the table narrow. Full timestamp lives in the row tooltip.
  return iso.slice(0, 10);
}

interface Props {
  rows: DeviceRow[];
  selection: RowSelectionState;
  onSelectionChange: OnChangeFn<RowSelectionState>;
  onRowClick?: (deviceId: string) => void;
  sortBy: DevicesSortBy | null;
  sortDir: DevicesSortDir;
  onSort: (column: DevicesSortBy) => void;
}

function SortHeader({
  label,
  column,
  sortBy,
  sortDir,
  onSort,
}: {
  label: string;
  column: DevicesSortBy;
  sortBy: DevicesSortBy | null;
  sortDir: DevicesSortDir;
  onSort: (c: DevicesSortBy) => void;
}) {
  const active = sortBy === column;
  const Icon = !active ? IconSelector : sortDir === "asc" ? IconChevronUp : IconChevronDown;
  return (
    <UnstyledButton
      onClick={() => onSort(column)}
      style={{ fontWeight: "inherit", fontSize: "inherit" }}
      aria-label={`Sort by ${label}`}
    >
      <Group gap={4} wrap="nowrap">
        <span>{label}</span>
        <Icon size={14} color={active ? undefined : "var(--mantine-color-dimmed)"} />
      </Group>
    </UnstyledButton>
  );
}

export function DevicesTable({
  rows,
  selection,
  onSelectionChange,
  onRowClick,
  sortBy,
  sortDir,
  onSort,
}: Props) {
  // Base URL for "Open in Home Assistant" links. The backend returns the
  // externally-configured HA URL if set (typically in dev via HA_EXTERNAL_URL);
  // otherwise we fall back to the current origin, which under HA ingress IS
  // the HA host so the deep link resolves correctly.
  const { data: config } = useQuery({
    queryKey: ["config"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/config");
      if (error) throw new Error(String(error));
      return data!;
    },
  });
  const haOrigin =
    config?.ha_external_url ||
    (typeof window !== "undefined" ? window.location.origin : "");
  const columns: ColumnDef<DeviceRow>[] = [
    {
      id: "select",
      header: ({ table }) => {
        // TanStack Table's getToggleAllRowsSelectedHandler only touches the
        // current page's rows — off-page selections survive. Handle it
        // manually so unchecking clears EVERYTHING (matching user intent),
        // while checking adds the current page on top of existing picks.
        const pageIds = table.getRowModel().rows.map((r) => r.id);
        const totalSelected = Object.values(selection).filter(Boolean).length;
        const allPageSelected =
          pageIds.length > 0 && pageIds.every((id) => selection[id]);
        const somePageSelected = pageIds.some((id) => selection[id]);
        return (
          <Checkbox
            aria-label="Select All"
            checked={allPageSelected}
            indeterminate={!allPageSelected && (somePageSelected || totalSelected > 0)}
            onChange={(e) => {
              if (e.currentTarget.checked) {
                const next = { ...selection };
                for (const id of pageIds) next[id] = true;
                onSelectionChange(next);
              } else {
                onSelectionChange({});
              }
            }}
          />
        );
      },
      cell: ({ row }) => (
        <Checkbox
          aria-label={`Select ${row.original.name}`}
          checked={row.getIsSelected()}
          onChange={row.getToggleSelectedHandler()}
        />
      ),
    },
    {
      id: "severity",
      header: () => (
        <SortHeader label="!" column="severity" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
      ),
      cell: ({ row }) =>
        row.original.highest_severity ? (
          <SeverityBadge
            severity={row.original.highest_severity}
            count={row.original.issue_count}
          />
        ) : null,
    },
    {
      id: "name",
      header: () => (
        <SortHeader label="Device Name" column="name" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
      ),
      accessorKey: "name",
    },
    {
      id: "room",
      header: () => (
        <SortHeader label="Room" column="room" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
      ),
      cell: ({ row }) => row.original.area_name ?? "—",
    },
    {
      id: "integration",
      header: () => (
        <SortHeader label="Integration" column="integration" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
      ),
      cell: ({ row }) => row.original.integration ?? "—",
    },
    {
      id: "created",
      header: () => (
        <SortHeader label="Created" column="created" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
      ),
      cell: ({ row }) => (
        <Tooltip label={row.original.created_at ?? "—"} disabled={!row.original.created_at}>
          <span>{fmtDate(row.original.created_at)}</span>
        </Tooltip>
      ),
    },
    {
      id: "modified",
      header: () => (
        <SortHeader label="Modified" column="modified" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
      ),
      cell: ({ row }) => (
        <Tooltip label={row.original.modified_at ?? "—"} disabled={!row.original.modified_at}>
          <span>{fmtDate(row.original.modified_at)}</span>
        </Tooltip>
      ),
    },
    {
      id: "link",
      header: "",
      cell: ({ row }) => (
        <Tooltip label="Open in Home Assistant">
          <ActionIcon
            component="a"
            href={`${haOrigin}/config/devices/device/${row.original.id}`}
            target="_blank"
            rel="noopener noreferrer"
            variant="subtle"
            size="sm"
            aria-label="Open in Home Assistant"
            onClick={(e) => e.stopPropagation()}
          >
            <IconExternalLink size={14} />
          </ActionIcon>
        </Tooltip>
      ),
    },
  ];

  const table = useReactTable({
    data: rows,
    columns,
    getCoreRowModel: getCoreRowModel(),
    state: { rowSelection: selection },
    onRowSelectionChange: onSelectionChange,
    getRowId: (row) => row.id,
    enableRowSelection: true,
  });

  return (
    <Table withTableBorder highlightOnHover>
      <Table.Thead>
        {table.getHeaderGroups().map((hg) => (
          <Table.Tr key={hg.id}>
            {hg.headers.map((h) => (
              <Table.Th key={h.id}>
                {flexRender(h.column.columnDef.header, h.getContext())}
              </Table.Th>
            ))}
          </Table.Tr>
        ))}
      </Table.Thead>
      <Table.Tbody>
        {table.getRowModel().rows.map((row) => (
          <Table.Tr
            key={row.id}
            onClick={(e) => {
              const target = e.target as HTMLElement;
              if (target.closest('input[type="checkbox"], label')) return;
              onRowClick?.(row.original.id);
            }}
            style={{ cursor: onRowClick ? "pointer" : undefined }}
          >
            {row.getVisibleCells().map((c) => (
              <Table.Td key={c.id}>
                {flexRender(c.column.columnDef.cell, c.getContext())}
              </Table.Td>
            ))}
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  );
}
