import { Checkbox, Group, Table, UnstyledButton } from "@mantine/core";
import { IconChevronDown, IconChevronUp, IconSelector } from "@tabler/icons-react";
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
  issue_count: number;
  highest_severity: "info" | "warning" | "error" | null;
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
  const columns: ColumnDef<DeviceRow>[] = [
    {
      id: "select",
      header: ({ table }) => (
        <Checkbox
          aria-label="Select All"
          checked={table.getIsAllRowsSelected()}
          indeterminate={table.getIsSomeRowsSelected()}
          onChange={table.getToggleAllRowsSelectedHandler()}
        />
      ),
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
