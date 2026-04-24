import { Anchor, Checkbox, Group, Table, Text, Tooltip, UnstyledButton } from "@mantine/core";
import {
  IconChevronDown,
  IconChevronUp,
  IconSelector,
} from "@tabler/icons-react";
import {
  type ColumnDef,
  type OnChangeFn,
  type RowSelectionState,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { Link } from "react-router-dom";

import { SeverityBadge } from "@/components/SeverityBadge";
import type { EntitiesSortBy, EntitiesSortDir } from "@/hooks/useEntities";

export interface EntityRow {
  entity_id: string;
  name: string | null;
  original_name: string | null;
  display_name: string;
  domain: string;
  platform: string | null;
  device_id: string | null;
  device_name: string | null;
  area_id: string | null;
  area_name: string | null;
  disabled_by: string | null;
  hidden_by: string | null;
  created_at: string | null;
  modified_at: string | null;
  issue_count: number;
  highest_severity: "info" | "warning" | "error" | null;
}

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  return iso.slice(0, 10);
}

interface Props {
  rows: EntityRow[];
  selection: RowSelectionState;
  onSelectionChange: OnChangeFn<RowSelectionState>;
  onRowClick?: (entityId: string) => void;
  sortBy: EntitiesSortBy | null;
  sortDir: EntitiesSortDir;
  onSort: (column: EntitiesSortBy) => void;
  /** TanStack-shaped {id: bool} from useColumnVisibility. */
  columnVisibility?: Record<string, boolean>;
}

function SortHeader({
  label,
  column,
  sortBy,
  sortDir,
  onSort,
}: {
  label: string;
  column: EntitiesSortBy;
  sortBy: EntitiesSortBy | null;
  sortDir: EntitiesSortDir;
  onSort: (c: EntitiesSortBy) => void;
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

export function EntitiesTable({
  rows,
  selection,
  onSelectionChange,
  onRowClick,
  sortBy,
  sortDir,
  onSort,
  columnVisibility,
}: Props) {
  const columns: ColumnDef<EntityRow>[] = [
    {
      id: "select",
      header: ({ table }) => {
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
          aria-label={`Select ${row.original.display_name}`}
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
      id: "entity_id",
      header: () => (
        <SortHeader
          label="Entity ID"
          column="entity_id"
          sortBy={sortBy}
          sortDir={sortDir}
          onSort={onSort}
        />
      ),
      accessorFn: (r) => r.entity_id,
      cell: ({ row }) => <Text ff="monospace" size="sm">{row.original.entity_id}</Text>,
    },
    {
      id: "name",
      header: () => (
        <SortHeader label="Name" column="name" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
      ),
      // Match HA's own display fallback: if the entity has no name of its
      // own (name + original_name both null) it inherits the owning device's
      // name. Dimmed to signal "inherited, not entity-authored".
      cell: ({ row }) => {
        if (row.original.name) return row.original.name;
        if (row.original.original_name)
          return <Text c="dimmed">{row.original.original_name}</Text>;
        if (row.original.device_name)
          return <Text c="dimmed">{row.original.device_name}</Text>;
        return "—";
      },
    },
    {
      id: "domain",
      header: () => (
        <SortHeader label="Domain" column="domain" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
      ),
      accessorFn: (r) => r.domain,
    },
    {
      id: "room",
      header: () => (
        <SortHeader label="Room" column="room" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
      ),
      cell: ({ row }) => row.original.area_name ?? "—",
    },
    {
      id: "device",
      header: () => (
        <SortHeader label="Device" column="device" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
      ),
      cell: ({ row }) => {
        const { device_id, device_name } = row.original;
        if (!device_id) return "—";
        return (
          <Anchor
            component={Link}
            to={`/devices?device=${encodeURIComponent(device_id)}`}
            onClick={(e) => e.stopPropagation()}
            size="sm"
          >
            {device_name ?? device_id}
          </Anchor>
        );
      },
    },
    {
      id: "issues",
      header: "Issues",
      cell: ({ row }) =>
        row.original.issue_count > 0 ? row.original.issue_count : "—",
    },
    {
      id: "integration",
      header: () => (
        <SortHeader
          label="Integration"
          column="integration"
          sortBy={sortBy}
          sortDir={sortDir}
          onSort={onSort}
        />
      ),
      cell: ({ row }) => row.original.platform ?? "—",
    },
    {
      id: "disabled",
      header: "Disabled",
      cell: ({ row }) => (row.original.disabled_by ? "Yes" : "—"),
    },
    {
      id: "hidden",
      header: "Hidden",
      cell: ({ row }) => (row.original.hidden_by ? "Yes" : "—"),
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
  ];

  const table = useReactTable({
    data: rows,
    columns,
    getCoreRowModel: getCoreRowModel(),
    state: {
      rowSelection: selection,
      columnVisibility: columnVisibility ?? {},
    },
    onRowSelectionChange: onSelectionChange,
    getRowId: (row) => row.entity_id,
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
              // Don't fire row-click for checkboxes or anchors (Device link).
              if (target.closest('input[type="checkbox"], label, a')) return;
              onRowClick?.(row.original.entity_id);
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
