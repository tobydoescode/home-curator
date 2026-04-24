import {
  ActionIcon,
  Alert,
  Button,
  Group,
  Select,
  Stack,
  Switch,
  Table,
  TextInput,
  Title,
} from "@mantine/core";
import { IconTrash } from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";

export interface EntityIdRoomOverride {
  area_id: string | null;
  enabled: boolean;
}

export interface EntityIdBlock {
  starts_with_room?: boolean;
  rooms?: EntityIdRoomOverride[];
}

interface Props {
  block: EntityIdBlock;
  onChange: (next: EntityIdBlock) => void;
}

// Derived snake_case pattern shown readonly. Mirrors the backend derivation.
const SNAKE_PATTERN = "^[a-z][a-z0-9_]*$";

export function EntityIdNamingSection({ block, onChange }: Props) {
  const rooms = block.rooms ?? [];
  const areas = useQuery({
    queryKey: ["areas"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/areas");
      if (error) throw new Error(String(error));
      return data ?? [];
    },
  });

  function patch(next: Partial<EntityIdBlock>): void {
    onChange({ ...block, ...next });
  }

  function updateRoom(i: number, r: Partial<EntityIdRoomOverride>): void {
    const next = [...rooms];
    next[i] = { ...next[i], ...r };
    patch({ rooms: next });
  }

  function removeRoom(i: number): void {
    patch({ rooms: rooms.filter((_, j) => j !== i) });
  }

  function addRoom(): void {
    patch({ rooms: [...rooms, { area_id: null, enabled: false }] });
  }

  const areaById = (id: string | null): string | null => {
    if (!id) return null;
    return areas.data?.find((a) => a.id === id)?.name ?? null;
  };

  return (
    <Stack>
      <TextInput
        label="Derived Pattern"
        readOnly
        value={SNAKE_PATTERN}
        description="Fixed snake_case; use the Friendly Name block to change friendly naming."
      />
      <Switch
        label="Starts with device name (or room if standalone)"
        checked={!!block.starts_with_room}
        onChange={(e) => {
          const v = e.currentTarget.checked;
          patch({ starts_with_room: v });
        }}
      />
      <Group justify="space-between">
        <Title order={5}>Per-Room Overrides (opt-out)</Title>
        <Button size="xs" onClick={addRoom}>
          + Add Override
        </Button>
      </Group>
      {rooms.length === 0 && (
        <Alert color="gray" variant="light">
          No room opt-outs yet.
        </Alert>
      )}
      {rooms.length > 0 && (
        <Table withTableBorder>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Room</Table.Th>
              <Table.Th>Enabled</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {rooms.map((r, i) => (
              <Table.Tr key={i}>
                <Table.Td>
                  <Select
                    aria-label={`Room ${i}`}
                    searchable
                    data={(areas.data ?? []).map((a) => ({
                      value: a.id,
                      label: a.name,
                    }))}
                    value={r.area_id ?? null}
                    onChange={(v) => updateRoom(i, { area_id: v })}
                  />
                </Table.Td>
                <Table.Td>
                  <Switch
                    aria-label={`${areaById(r.area_id) ?? "Row"} enabled`}
                    checked={r.enabled}
                    onChange={(e) => {
                      const v = e.currentTarget.checked;
                      updateRoom(i, { enabled: v });
                    }}
                  />
                </Table.Td>
                <Table.Td>
                  <ActionIcon
                    variant="subtle"
                    color="red"
                    onClick={() => removeRoom(i)}
                  >
                    <IconTrash size={16} />
                  </ActionIcon>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Stack>
  );
}
