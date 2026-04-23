import { ActionIcon, Badge, Button, Group, Stack, Table, Text, Title } from "@mantine/core";
import { IconEdit, IconFlask, IconTrash } from "@tabler/icons-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { applyCustomRuleEdit } from "@/pages/Settings/applyCustomRuleEdit";
import { CustomRuleEditor, type CustomRule } from "@/pages/Settings/CustomRuleEditor";
import type { SectionProps } from "./NamingSection";

export interface CustomRulesSectionProps extends SectionProps {
  /** Which scope's custom rules this section edits. Defaults to "devices". */
  scope?: "devices" | "entities";
}

export function CustomRulesSection({
  draft,
  onChange,
  scope = "devices",
}: CustomRulesSectionProps) {
  const navigate = useNavigate();
  const [editing, setEditing] = useState<number | "new" | null>(null);

  const customs = draft.policies
    .map((p, i) => ({ p, i }))
    .filter(
      ({ p }) =>
        p.type === "custom" &&
        ((p as { scope?: string }).scope ?? "devices") === scope,
    );

  function remove(i: number) {
    const policies = draft.policies.filter((_, j) => j !== i);
    onChange({ ...draft, policies });
  }

  function openNew() {
    setEditing("new");
  }

  function handleSaved(rule: CustomRule, slot: number | "new") {
    // Lock new rules to the current scope so they land under the right page.
    const scoped = slot === "new" ? { ...rule, scope } : rule;
    onChange(applyCustomRuleEdit(draft, scoped, slot));
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
          scope={scope}
          onClose={() => setEditing(null)}
          onSaved={(rule) => handleSaved(rule, editing)}
        />
      )}
    </Stack>
  );
}
