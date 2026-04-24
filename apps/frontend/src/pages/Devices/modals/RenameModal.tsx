import { Button, Group, Stack, TextInput } from "@mantine/core";
import { useState } from "react";

import { useUpdateDevice } from "@/hooks/useActions";

interface Props {
  deviceId: string;
  currentName: string;
  onClose: () => void;
}

export function RenameModal({ deviceId, currentName, onClose }: Props) {
  const [name, setName] = useState(currentName);
  const rename = useUpdateDevice();
  return (
    <Stack>
      <TextInput
        label="Name"
        value={name}
        onChange={(e) => setName(e.currentTarget.value)}
        required
      />
      <Group justify="flex-end">
        <Button variant="subtle" onClick={onClose}>
          Cancel
        </Button>
        <Button
          disabled={!name || name === currentName || rename.isPending}
          loading={rename.isPending}
          onClick={async () => {
            await rename.mutateAsync({
              device_id: deviceId,
              changes: { name_by_user: name },
            });
            onClose();
          }}
        >
          Rename
        </Button>
      </Group>
    </Stack>
  );
}
