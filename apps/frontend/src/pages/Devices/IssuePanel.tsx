import { Button, Drawer, Group, Stack, Text, Textarea } from "@mantine/core";
import { useState } from "react";

import { SeverityBadge } from "@/components/SeverityBadge";
import {
  useAcknowledgeException,
  useClearException,
} from "@/hooks/useExceptions";

export interface IssueItem {
  policy_id: string;
  rule_type: string;
  severity: "info" | "warning" | "error";
  message: string;
}

interface Props {
  opened: boolean;
  onClose: () => void;
  deviceId: string | null;
  deviceName?: string;
  issues: IssueItem[];
}

export function IssuePanel({
  opened,
  onClose,
  deviceId,
  deviceName,
  issues,
}: Props) {
  const ack = useAcknowledgeException();
  const clear = useClearException();
  const [notes, setNotes] = useState<Record<string, string>>({});
  if (!deviceId) return null;
  return (
    <Drawer
      opened={opened}
      onClose={onClose}
      title={deviceName ?? deviceId}
      position="right"
    >
      <Stack>
        {issues.length === 0 && <Text c="dimmed">No Issues</Text>}
        {issues.map((issue) => (
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
                    device_id: deviceId,
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
                  clear.mutate({ device_id: deviceId, policy_id: issue.policy_id })
                }
              >
                Clear Exception
              </Button>
            </Group>
          </Stack>
        ))}
      </Stack>
    </Drawer>
  );
}
