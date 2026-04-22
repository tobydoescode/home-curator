import { Button, Checkbox, Group, Loader, Stack, Table, Text, Title } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useState } from "react";

import { useBulkDeleteExceptions, useExceptionsList } from "@/hooks/useExceptions";

export function ExceptionsPage() {
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const list = useExceptionsList({ page: 1, page_size: 50 });
  const bulk = useBulkDeleteExceptions();

  if (list.isLoading) return <Loader />;
  if (list.error) return <Text c="red">{String(list.error)}</Text>;
  const rows = list.data?.exceptions ?? [];
  const total = list.data?.total ?? 0;

  function toggle(id: number) {
    setSelected((prev) => {
      const n = new Set(prev);
      if (n.has(id)) n.delete(id); else n.add(id);
      return n;
    });
  }

  async function removeSelected() {
    try {
      await bulk.mutateAsync(Array.from(selected));
      const count = selected.size;
      setSelected(new Set());
      notifications.show({ color: "green", title: "Removed", message: `${count} exception(s) removed.` });
    } catch (e) {
      notifications.show({ color: "red", title: "Remove Failed", message: String(e) });
    }
  }

  return (
    <Stack>
      <Title order={3}>Exceptions</Title>
      <Text c="dimmed">{total} acknowledged exceptions</Text>
      {total === 0 ? (
        <Text>No exceptions yet. Open a device in the Devices view and acknowledge an issue to create one.</Text>
      ) : (
        <>
          {selected.size > 0 && (
            <Group>
              <Button color="red" onClick={removeSelected} loading={bulk.isPending}>
                Remove Selected ({selected.size})
              </Button>
              <Button variant="default" onClick={() => setSelected(new Set())}>Clear Selection</Button>
            </Group>
          )}
          <Table>
            <Table.Thead>
              <Table.Tr>
                <Table.Th />
                <Table.Th>Device</Table.Th>
                <Table.Th>Policy</Table.Th>
                <Table.Th>Room</Table.Th>
                <Table.Th>Acknowledged At</Table.Th>
                <Table.Th>Note</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {rows.map((r) => (
                <Table.Tr key={r.id ?? `${r.device_id}-${r.policy_id}`}>
                  <Table.Td>
                    <Checkbox
                      aria-label={`Select exception ${r.id}`}
                      checked={r.id != null && selected.has(r.id)}
                      onChange={() => r.id != null && toggle(r.id)}
                    />
                  </Table.Td>
                  <Table.Td>{r.device_name ?? r.device_id}</Table.Td>
                  <Table.Td>{r.policy_name ?? r.policy_id}</Table.Td>
                  <Table.Td>{r.device_area_name ?? "—"}</Table.Td>
                  <Table.Td>{r.acknowledged_at}</Table.Td>
                  <Table.Td>{r.note ?? "—"}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </>
      )}
    </Stack>
  );
}
