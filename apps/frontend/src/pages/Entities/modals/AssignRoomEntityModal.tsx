import { Button, Group, Select, Stack, Text } from "@mantine/core";
import { useState } from "react";

import { useAssignRoomEntities } from "@/hooks/useEntityActions";

interface Props {
  entityIds: string[];
  rooms: { id: string; name: string }[];
  onClose: () => void;
}

export function AssignRoomEntityModal({ entityIds, rooms, onClose }: Props) {
  const [areaId, setAreaId] = useState<string | null>(null);
  const assign = useAssignRoomEntities();
  return (
    <Stack>
      <Text>
        Assigning a room to <strong>{entityIds.length}</strong>{" "}
        {entityIds.length === 1 ? "entity" : "entities"}.
      </Text>
      <Select
        label="Room"
        data={rooms.map((r) => ({ value: r.id, label: r.name }))}
        value={areaId}
        onChange={setAreaId}
        searchable
        required
      />
      <Group justify="flex-end">
        <Button variant="subtle" onClick={onClose}>
          Cancel
        </Button>
        <Button
          disabled={!areaId || assign.isPending}
          loading={assign.isPending}
          onClick={async () => {
            await assign.mutateAsync({ entity_ids: entityIds, area_id: areaId! });
            onClose();
          }}
        >
          Assign
        </Button>
      </Group>
    </Stack>
  );
}
