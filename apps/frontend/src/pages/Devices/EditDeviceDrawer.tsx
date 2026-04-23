import {
  Button,
  Divider,
  Drawer,
  Group,
  Select,
  Stack,
  Text,
  Textarea,
  TextInput,
} from "@mantine/core";
import { modals } from "@mantine/modals";
import { useEffect, useState } from "react";

import { SeverityBadge } from "@/components/SeverityBadge";
import { useUpdateDevice } from "@/hooks/useActions";
import {
  useAcknowledgeException,
  useClearException,
} from "@/hooks/useExceptions";

export interface EditDeviceDrawerDevice {
  id: string;
  name: string;
  name_by_user: string | null;
  area_id: string | null;
  area_name: string | null;
  issues: Array<{
    policy_id: string;
    rule_type: string;
    severity: "info" | "warning" | "error";
    message: string;
  }>;
}

interface Props {
  opened: boolean;
  onClose: () => void;
  device: EditDeviceDrawerDevice | null;
  areas: { id: string; name: string }[];
}

export function EditDeviceDrawer({ opened, onClose, device, areas }: Props) {
  const initialName = device ? (device.name_by_user ?? device.name) : "";
  const initialAreaId = device?.area_id ?? null;

  const [name, setName] = useState(initialName);
  const [areaId, setAreaId] = useState<string | null>(initialAreaId);
  const update = useUpdateDevice();
  const ack = useAcknowledgeException();
  const clear = useClearException();
  const [notes, setNotes] = useState<Record<string, string>>({});

  // Re-seed when the active device changes (drawer stays mounted across clicks).
  useEffect(() => {
    setName(initialName);
    setAreaId(initialAreaId);
  }, [device?.id]);

  if (!device) return null;

  const trimmedName = name.trim();
  const isDirty = trimmedName !== initialName || areaId !== initialAreaId;
  const canSave = isDirty && trimmedName.length > 0 && !update.isPending;

  const save = () => {
    if (!canSave || !device) return;
    const changes: { name_by_user?: string | null; area_id?: string | null } = {};
    if (trimmedName !== initialName) changes.name_by_user = trimmedName;
    if (areaId !== initialAreaId) changes.area_id = areaId;
    update.mutate({ device_id: device.id, changes });
  };

  const requestClose = () => {
    if (!isDirty) {
      onClose();
      return;
    }
    modals.openConfirmModal({
      title: "Discard changes?",
      children: "You have unsaved changes on this device.",
      labels: { confirm: "Discard", cancel: "Keep editing" },
      confirmProps: { color: "red" },
      onConfirm: onClose,
    });
  };

  return (
    <Drawer
      opened={opened}
      onClose={requestClose}
      title={device.name_by_user ?? device.name}
      position="right"
    >
      <Stack>
        <TextInput
          label="Name"
          value={name}
          onChange={(e) => setName(e.currentTarget.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              save();
            }
          }}
        />
        <Select
          label="Room"
          data={areas.map((a) => ({ value: a.id, label: a.name }))}
          value={areaId}
          onChange={setAreaId}
          searchable
          clearable
        />
        <Group justify="flex-end">
          <Button variant="subtle" onClick={requestClose}>
            Cancel
          </Button>
          <Button disabled={!canSave} onClick={save} loading={update.isPending}>
            Save
          </Button>
        </Group>
        {device.issues.length > 0 && <Divider my="sm" />}
        {device.issues.length === 0 ? null : (
          <Stack gap="md">
            {device.issues.map((issue) => (
              <Stack key={issue.policy_id} gap="xs">
                <Group>
                  <SeverityBadge severity={issue.severity} count={1} />
                  <Text fw={500}>{issue.message}</Text>
                </Group>
                <Text size="xs" c="dimmed">
                  Rule: {issue.rule_type} · Policy: {issue.policy_id}
                </Text>
                <Textarea
                  placeholder="Optional Note"
                  value={notes[issue.policy_id] ?? ""}
                  onChange={(e) => {
                    const value = e.currentTarget.value;
                    setNotes((n) => ({ ...n, [issue.policy_id]: value }));
                  }}
                />
                <Group gap="xs">
                  <Button
                    size="xs"
                    onClick={() =>
                      ack.mutate({
                        device_id: device.id,
                        policy_id: issue.policy_id,
                        note: notes[issue.policy_id],
                      })
                    }
                    loading={ack.isPending}
                  >
                    Acknowledge As Exception
                  </Button>
                  <Button
                    size="xs"
                    variant="subtle"
                    onClick={() =>
                      clear.mutate({
                        device_id: device.id,
                        policy_id: issue.policy_id,
                      })
                    }
                  >
                    Clear Exception
                  </Button>
                </Group>
              </Stack>
            ))}
          </Stack>
        )}
      </Stack>
    </Drawer>
  );
}
