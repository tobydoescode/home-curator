import { Group, Pagination, Select, Text } from "@mantine/core";

interface Props {
  total: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;
}

export function PaginationFooter({
  total,
  page,
  pageSize,
  onPageChange,
  onPageSizeChange,
}: Props) {
  const start = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <Group justify="space-between">
      <Group gap="xs">
        <Text size="sm" c="dimmed">
          Showing {start}–{end} of {total}
        </Text>
        <Select
          data={["25", "50", "100", "250"]}
          value={String(pageSize)}
          onChange={(v) => onPageSizeChange(Number(v ?? 50))}
          w={110}
        />
      </Group>
      <Pagination total={totalPages} value={page} onChange={onPageChange} />
    </Group>
  );
}
