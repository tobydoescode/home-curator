import { Code, List, Stack, Text } from "@mantine/core";
import { modals } from "@mantine/modals";

export interface RenameConfirmArgs {
  oldId: string;
  newId: string;
  onConfirm: () => void;
}

export function openRenameConfirmModal({
  oldId,
  newId,
  onConfirm,
}: RenameConfirmArgs): void {
  modals.openConfirmModal({
    title: "Rename Entity ID?",
    children: (
      <Stack gap="xs">
        <Text size="sm">
          <Code>{oldId}</Code> &rarr; <Code>{newId}</Code>
        </Text>
        <Text size="sm">
          This renames the HA entity registry slug. HA attempts to update
          references in automations, scripts, and scenes, but the following
          are NOT automatically updated:
        </Text>
        <List size="sm" withPadding>
          <List.Item>Template entities / sensors</List.Item>
          <List.Item>Lovelace dashboards (cards that reference by id)</List.Item>
          <List.Item>External integrations (e.g. Spook)</List.Item>
          <List.Item>Any YAML config outside the device registry</List.Item>
        </List>
        <Text size="sm" c="dimmed">
          You'll need to check these yourself.
        </Text>
      </Stack>
    ),
    labels: { confirm: "Rename", cancel: "Keep" },
    confirmProps: { color: "red" },
    onConfirm,
  });
}
