import { ActionIcon, Badge, Button, Group, Stack, Table, Text, Title } from "@mantine/core";
import { IconEdit, IconFlask, IconTrash } from "@tabler/icons-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { applyCustomRuleEdit } from "@/pages/Settings/applyCustomRuleEdit";
import { CustomRuleEditor, type CustomRule } from "@/pages/Settings/CustomRuleEditor";
import type { SectionProps } from "./NamingSection";

export function CustomRulesSection({ draft, onChange }: SectionProps) {
  const navigate = useNavigate();
  const [editing, setEditing] = useState<number | "new" | null>(null);

  const customs = draft.policies
    .map((p, i) => ({ p, i }))
    .filter(({ p }) => p.type === "custom");

  function remove(i: number) {
    const policies = draft.policies.filter((_, j) => j !== i);
    onChange({ ...draft, policies });
  }

  function openNew() {
    setEditing("new");
  }

  function handleSaved(rule: CustomRule, slot: number | "new") {
    onChange(applyCustomRuleEdit(draft, rule, slot));
    setEditing(null);
  }

  function handleTest(ruleId: string) {
    navigate(`/settings/global?test=${encodeURIComponent(ruleId)}`);
  }

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={4}>Custom Rules</Title>
        <Button size="xs" onClick={openNew}>+ Add Custom Rule</Button>
      </Group>
      {customs.length === 0 && <Text c="dimmed">No custom rules yet.</Text>}
      {customs.length > 0 && (
        <Table withTableBorder>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Enabled</Table.Th>
              <Table.Th>Name</Table.Th>
              <Table.Th>Severity</Table.Th>
              <Table.Th>Message</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {customs.map(({ p, i }) => (
              <Table.Tr key={p.id}>
                <Table.Td>{p.enabled ? "✓" : ""}</Table.Td>
                <Table.Td>{p.id}</Table.Td>
                <Table.Td><Badge>{(p as any).severity}</Badge></Table.Td>
                <Table.Td style={{ maxWidth: 360 }}>
                  <Text size="sm" truncate>{(p as any).message}</Text>
                </Table.Td>
                <Table.Td>
                  <Group gap="xs">
                    <ActionIcon variant="subtle" onClick={() => setEditing(i)} aria-label="Edit">
                      <IconEdit size={16} />
                    </ActionIcon>
                    <ActionIcon variant="subtle" onClick={() => handleTest(p.id)} aria-label="Test">
                      <IconFlask size={16} />
                    </ActionIcon>
                    <ActionIcon variant="subtle" color="red" onClick={() => remove(i)} aria-label="Delete">
                      <IconTrash size={16} />
                    </ActionIcon>
                  </Group>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      {editing !== null && (
        <CustomRuleEditor
          initial={editing === "new" ? null : (customs.find(({ i }) => i === editing)!.p as any)}
          onClose={() => setEditing(null)}
          onSaved={(rule) => handleSaved(rule, editing)}
        />
      )}
    </Stack>
  );
}
