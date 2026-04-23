import { Button, Group, Menu, Paper, Stack, Text } from "@mantine/core";
import { modals } from "@mantine/modals";

import { useDeleteEntities, useEntityState } from "@/hooks/useEntityActions";
import { AssignRoomEntityModal } from "./modals/AssignRoomEntityModal";

interface Props {
  selectedIds: string[];
  rooms: { id: string; name: string }[];
  onClearSelection: () => void;
}

export function ActionRow({ selectedIds, rooms, onClearSelection }: Props) {
  const entityState = useEntityState();
  const deleteEntities = useDeleteEntities();

  if (selectedIds.length === 0) return null;

  const openAssignRoom = () =>
    modals.open({
      title: "Assign Room",
      children: (
        <AssignRoomEntityModal
          entityIds={selectedIds}
          rooms={rooms}
          onClose={() => modals.closeAll()}
        />
      ),
    });

  const openRenameComingSoon = () =>
    modals.open({
      title: "Coming Soon",
      children: (
        <Stack>
          <Text size="sm">
            Bulk Rename (single + dual-regex pattern) lands in Plan 5. The
            backend endpoint is live; the modal UI is the next slice.
          </Text>
          <Group justify="flex-end">
            <Button variant="subtle" onClick={() => modals.closeAll()}>
              Close
            </Button>
          </Group>
        </Stack>
      ),
    });

  const fireState = (
    field: "disabled_by" | "hidden_by",
    value: "user" | null,
  ) => {
    entityState.mutate(
      { entity_ids: selectedIds, field, value },
      { onSuccess: () => onClearSelection() },
    );
  };

  const openDelete = () =>
    modals.openConfirmModal({
      title: `Delete ${selectedIds.length} ${selectedIds.length === 1 ? "entity" : "entities"}?`,
      children:
        "This cannot be undone. Some entities may fail to delete if their integration does not allow it.",
      labels: { confirm: "Delete", cancel: "Keep" },
      confirmProps: { color: "red" },
      onConfirm: () => {
        deleteEntities.mutate(selectedIds, {
          onSuccess: () => onClearSelection(),
        });
      },
    });

  return (
    <Paper withBorder p="xs" bg="indigo.0">
      <Group justify="space-between">
        <Text size="sm" fw={600} c="indigo.9">
          {selectedIds.length}{" "}
          {selectedIds.length === 1 ? "Entity" : "Entities"} Selected
        </Text>
        <Group gap="xs">
          <Button size="xs" variant="default" onClick={openAssignRoom}>
            Assign Room…
          </Button>
          <Button size="xs" variant="default" onClick={openRenameComingSoon}>
            Rename…
          </Button>
          <Menu>
            <Menu.Target>
              <Button size="xs" variant="default">
                ⋯ More
              </Button>
            </Menu.Target>
            <Menu.Dropdown>
              <Menu.Item onClick={() => fireState("disabled_by", null)}>
                Enable
              </Menu.Item>
              <Menu.Item onClick={() => fireState("disabled_by", "user")}>
                Disable
              </Menu.Item>
              <Menu.Item onClick={() => fireState("hidden_by", null)}>
                Show
              </Menu.Item>
              <Menu.Item onClick={() => fireState("hidden_by", "user")}>
                Hide
              </Menu.Item>
              <Menu.Divider />
              <Menu.Item disabled>Acknowledge Exception…</Menu.Item>
            </Menu.Dropdown>
          </Menu>
          <Button
            size="xs"
            color="red"
            variant="light"
            onClick={openDelete}
            loading={deleteEntities.isPending}
          >
            Delete
          </Button>
        </Group>
      </Group>
    </Paper>
  );
}
