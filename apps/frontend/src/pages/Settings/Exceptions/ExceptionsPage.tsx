import {
  Badge,
  Button,
  Checkbox,
  Group,
  Loader,
  Stack,
  Table,
  Text,
  Title,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  useBulkDeleteExceptions,
  useExceptionsList,
} from "@/hooks/useExceptions";

interface Row {
  id: number | null | undefined;
  target_kind?: "device" | "entity";
  device_id?: string | null;
  entity_id?: string | null;
  target_name?: string | null;
  target_area_name?: string | null;
  device_name?: string | null;
  device_area_name?: string | null;
  policy_id: string;
  policy_name?: string | null;
  acknowledged_at: string;
  note?: string | null;
}

export function ExceptionsPage() {
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const list = useExceptionsList({ page: 1, page_size: 50 });
  const bulk = useBulkDeleteExceptions();
  const navigate = useNavigate();

  if (list.isLoading) return <Loader />;
  if (list.error) return <Text c="red">{String(list.error)}</Text>;
  const rows = (list.data?.exceptions ?? []) as unknown as Row[];
  const total = list.data?.total ?? 0;

  function toggle(id: number) {
    setSelected((prev) => {
      const n = new Set(prev);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });
  }

  async function removeSelected() {
    try {
      await bulk.mutateAsync(Array.from(selected));
      const count = selected.size;
      setSelected(new Set());
      notifications.show({
        color: "green",
        title: "Removed",
        message: `${count} exception(s) removed.`,
      });
    } catch (e) {
      notifications.show({
        color: "red",
        title: "Remove Failed",
        message: String(e),
      });
    }
  }

  function onRowClick(r: Row): void {
    const kind = r.target_kind ?? (r.device_id ? "device" : "entity");
    if (kind === "device" && r.device_id) {
      navigate(`/devices?device=${r.device_id}`);
    } else if (kind === "entity" && r.entity_id) {
      navigate(`/entities?entity=${encodeURIComponent(r.entity_id)}`);
    }
  }

  return (
    <Stack>
      <Title order={3}>Exceptions</Title>
      <Text c="dimmed">{total} acknowledged exceptions</Text>
      {total === 0 ? (
        <Text>
          No exceptions yet. Open a device or entity and acknowledge an issue
          to create one.
        </Text>
      ) : (
        <>
          {selected.size > 0 && (
            <Group>
              <Button
                color="red"
                onClick={removeSelected}
                loading={bulk.isPending}
              >
                Remove Selected ({selected.size})
              </Button>
              <Button
                variant="default"
                onClick={() => setSelected(new Set())}
              >
                Clear Selection
              </Button>
            </Group>
          )}
          <Table highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th />
                <Table.Th>Target</Table.Th>
                <Table.Th>Policy</Table.Th>
                <Table.Th>Room</Table.Th>
                <Table.Th>Acknowledged At</Table.Th>
                <Table.Th>Note</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {rows.map((r) => {
                const kind =
                  r.target_kind ?? (r.device_id ? "device" : "entity");
                const name =
                  r.target_name ??
                  r.device_name ??
                  r.device_id ??
                  r.entity_id;
                return (
                  <Table.Tr
                    key={r.id ?? `${r.device_id ?? r.entity_id}-${r.policy_id}`}
                    style={{ cursor: "pointer" }}
                    onClick={() => onRowClick(r)}
                  >
                    <Table.Td onClick={(e) => e.stopPropagation()}>
                      <Checkbox
                        aria-label={`Select exception ${r.id}`}
                        checked={r.id != null && selected.has(r.id)}
                        onChange={() => r.id != null && toggle(r.id)}
                      />
                    </Table.Td>
                    <Table.Td>
                      <Group gap="xs">
                        <Badge size="xs">{kind}</Badge>
                        <Text size="sm">{name}</Text>
                      </Group>
                    </Table.Td>
                    <Table.Td>{r.policy_name ?? r.policy_id}</Table.Td>
                    <Table.Td>
                      {r.target_area_name ?? r.device_area_name ?? "—"}
                    </Table.Td>
                    <Table.Td>{r.acknowledged_at}</Table.Td>
                    <Table.Td>{r.note ?? "—"}</Table.Td>
                  </Table.Tr>
                );
              })}
            </Table.Tbody>
          </Table>
        </>
      )}
    </Stack>
  );
}
