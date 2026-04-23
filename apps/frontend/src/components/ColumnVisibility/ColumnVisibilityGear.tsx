import {
  ActionIcon,
  Button,
  Checkbox,
  Group,
  Popover,
  Stack,
  Text,
} from "@mantine/core";
import { IconColumns } from "@tabler/icons-react";
import { useState } from "react";

export interface ColumnDescriptor {
  id: string;
  /** Human-readable label shown next to the checkbox. */
  label: string;
}

interface Props {
  columns: ColumnDescriptor[];
  visible: Record<string, boolean>;
  onToggle: (id: string) => void;
  onReset: () => void;
}

export function ColumnVisibilityGear({
  columns,
  visible,
  onToggle,
  onReset,
}: Props) {
  const [opened, setOpened] = useState(false);

  return (
    <Popover
      opened={opened}
      onChange={setOpened}
      position="bottom-end"
      withinPortal
      shadow="md"
      trapFocus
    >
      <Popover.Target>
        <ActionIcon
          variant="default"
          size={32}
          aria-label="Columns"
          onClick={() => setOpened((o) => !o)}
        >
          <IconColumns size={16} />
        </ActionIcon>
      </Popover.Target>
      <Popover.Dropdown>
        <Stack gap="xs" miw={200}>
          <Text size="xs" fw={600} c="dimmed">
            Visible Columns
          </Text>
          {columns.map((c) => (
            <Checkbox
              key={c.id}
              label={c.label}
              checked={Boolean(visible[c.id])}
              onChange={() => onToggle(c.id)}
            />
          ))}
          <Group justify="flex-end" mt="xs">
            <Button size="xs" variant="subtle" onClick={onReset}>
              Reset to defaults
            </Button>
          </Group>
        </Stack>
      </Popover.Dropdown>
    </Popover>
  );
}
