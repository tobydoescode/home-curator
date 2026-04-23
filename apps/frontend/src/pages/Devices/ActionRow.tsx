import { Button, Group, Menu, Paper, Text } from "@mantine/core";
import { modals } from "@mantine/modals";

import { useDeleteDevices } from "@/hooks/useActions";
import type { DeviceRow } from "./DevicesTable";
import { AssignRoomModal } from "./modals/AssignRoomModal";
import { RenameModal } from "./modals/RenameModal";
import { RenamePatternModal } from "./modals/RenamePatternModal";

interface Props {
  selectedIds: string[];
  rooms: { id: string; name: string }[];
  deviceLookup: Record<string, DeviceRow>;
  onClearSelection: () => void;
}

export function ActionRow({
  selectedIds,
  rooms,
  deviceLookup,
  onClearSelection,
}: Props) {
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

  const deleteDevices = useDeleteDevices();

  const openDelete = () => {
    modals.openConfirmModal({
      title: `Delete ${selectedIds.length} ${selectedIds.length === 1 ? "device" : "devices"}?`,
      children:
        "This cannot be undone. Some devices may fail to delete if their integration does not allow it.",
      labels: { confirm: "Delete", cancel: "Keep" },
      confirmProps: { color: "red" },
      onConfirm: () => {
        // Clear on any HTTP success — partial failures stay visible in
        // the table and are communicated via the hook's yellow toast.
        deleteDevices.mutate(selectedIds, {
          onSuccess: () => onClearSelection(),
        });
      },
    });
  };

  return (
    <Paper withBorder p="xs" bg="indigo.0">
      <Group justify="space-between">
        <Text size="sm" fw={600} c="indigo.9">
          {selectedIds.length} {selectedIds.length === 1 ? "Device" : "Devices"} Selected
        </Text>
        <Group gap="xs">
          <Button
            size="xs"
            color="red"
            variant="light"
            onClick={openDelete}
            loading={deleteDevices.isPending}
          >
            Delete
          </Button>
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
