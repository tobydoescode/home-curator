import { Button, Group, Menu, Paper, Text } from "@mantine/core";
import { modals } from "@mantine/modals";

import type { DeviceRow } from "./DevicesTable";
import { AssignRoomModal } from "./modals/AssignRoomModal";
import { RenameModal } from "./modals/RenameModal";
import { RenamePatternModal } from "./modals/RenamePatternModal";

interface Props {
  selectedIds: string[];
  rooms: { id: string; name: string }[];
  deviceLookup: Record<string, DeviceRow>;
}

export function ActionRow({ selectedIds, rooms, deviceLookup }: Props) {
  if (selectedIds.length === 0) return null;

  const openAssignRoom = () =>
    modals.open({
      title: "Assign Room",
      children: (
        <AssignRoomModal
          deviceIds={selectedIds}
          rooms={rooms}
          onClose={() => modals.closeAll()}
        />
      ),
    });

  const openRename = () => {
    if (selectedIds.length !== 1) return;
    const d = deviceLookup[selectedIds[0]];
    if (!d) return;
    modals.open({
      title: "Rename Device",
      children: (
        <RenameModal
          deviceId={d.id}
          currentName={d.name}
          onClose={() => modals.closeAll()}
        />
      ),
    });
  };

  const openRenamePattern = () =>
    modals.open({
      title: "Rename (Pattern)",
      children: (
        <RenamePatternModal
          deviceIds={selectedIds}
          onClose={() => modals.closeAll()}
        />
      ),
    });

  return (
    <Paper withBorder p="xs" bg="indigo.0">
      <Group justify="space-between">
        <Text size="sm" fw={600} c="indigo.9">
          {selectedIds.length} {selectedIds.length === 1 ? "Device" : "Devices"} Selected
        </Text>
        <Group gap="xs">
          <Button size="xs" variant="default" onClick={openAssignRoom}>
            Assign Room…
          </Button>
          <Menu>
            <Menu.Target>
              <Button size="xs" variant="default">
                ⋯ More
              </Button>
            </Menu.Target>
            <Menu.Dropdown>
              <Menu.Item
                disabled={selectedIds.length !== 1}
                onClick={openRename}
              >
                Rename…
              </Menu.Item>
              <Menu.Item onClick={openRenamePattern}>Rename (Pattern)…</Menu.Item>
              <Menu.Item disabled>Assign Battery Entity…</Menu.Item>
              <Menu.Item disabled>Assign Connectivity Entity…</Menu.Item>
            </Menu.Dropdown>
          </Menu>
        </Group>
      </Group>
    </Paper>
  );
}
