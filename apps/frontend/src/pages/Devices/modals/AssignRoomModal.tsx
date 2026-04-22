import { Button, Group, Select, Stack, Text } from "@mantine/core";
import { useState } from "react";

import { useAssignRoom } from "@/hooks/useActions";

interface Props {
  deviceIds: string[];
  rooms: { id: string; name: string }[];
  onClose: () => void;
}

export function AssignRoomModal({ deviceIds, rooms, onClose }: Props) {
  const [areaId, setAreaId] = useState<string | null>(null);
  const assign = useAssignRoom();
  return (
    <Stack>
      <Text>
        Assigning a room to <strong>{deviceIds.length}</strong>{" "}
        {deviceIds.length === 1 ? "device" : "devices"}.
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
            await assign.mutateAsync({ device_ids: deviceIds, area_id: areaId! });
            onClose();
          }}
        >
          Assign
        </Button>
      </Group>
    </Stack>
  );
}
