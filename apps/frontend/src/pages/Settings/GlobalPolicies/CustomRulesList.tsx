import { ActionIcon, Badge, Button, Card, Group, Stack, Switch, Text, TextInput, Title } from "@mantine/core";
import { IconEdit, IconFlask, IconTrash } from "@tabler/icons-react";
import { useState } from "react";

import type { PoliciesFileShape } from "@/hooks/usePolicies";

export interface CustomRulesListProps {
  draft: PoliciesFileShape;
  onChange: (d: PoliciesFileShape) => void;
  onEdit: (index: number) => void;
  onAdd: () => void;
  onTest: (index: number) => void;
}

export function CustomRulesList({ draft, onChange, onEdit, onAdd, onTest }: CustomRulesListProps) {
  const [filter, setFilter] = useState<"all" | "on" | "off">("all");
  const [search, setSearch] = useState("");

  const customs = draft.policies
    .map((p, i) => ({ p: p as any, i }))
    .filter(({ p }) => p.type === "custom")
    .filter(({ p }) => filter === "all" || (filter === "on" ? p.enabled : !p.enabled))
    .filter(({ p }) =>
      !search ||
      p.id.toLowerCase().includes(search.toLowerCase()) ||
      (p.message ?? "").toLowerCase().includes(search.toLowerCase()),
    );

  function togglePatch(i: number, next: Record<string, unknown>) {
    const policies = [...draft.policies];
    policies[i] = { ...policies[i], ...next } as typeof policies[number];
    onChange({ ...draft, policies });
  }

  function remove(i: number) {
    const policies = draft.policies.filter((_, j) => j !== i);
    onChange({ ...draft, policies });
  }

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={4}>Custom Rules</Title>
        <Button size="xs" onClick={onAdd}>+ Add Custom Rule</Button>
      </Group>
      <Group>
        <TextInput
          placeholder="Search name or message"
          aria-label="Search"
          value={search}
          onChange={(e) => setSearch(e.currentTarget.value)}
          style={{ flex: 1 }}
        />
        <select aria-label="Enabled filter" value={filter} onChange={(e) => setFilter(e.currentTarget.value as any)}>
          <option value="all">All</option>
          <option value="on">Enabled</option>
          <option value="off">Disabled</option>
        </select>
      </Group>
      {customs.length === 0 && <Text c="dimmed">No custom rules match.</Text>}
      {customs.map(({ p, i }) => (
        <Card key={p.id} withBorder padding="sm">
          <Group justify="space-between" align="flex-start">
            <Stack gap={2}>
              <Group gap="xs">
                <Switch
                  aria-label={`Enable ${p.id}`}
                  checked={p.enabled}
                  onChange={(e) => togglePatch(i, { enabled: e.currentTarget.checked })}
                />
                <Text fw={600}>{p.id}</Text>
                <Badge size="xs">{p.severity}</Badge>
              </Group>
              <Text size="sm" c="dimmed" lineClamp={1}>{p.message}</Text>
            </Stack>
            <Group gap="xs">
              <ActionIcon variant="subtle" onClick={() => onEdit(i)} aria-label="Edit"><IconEdit size={16} /></ActionIcon>
              <ActionIcon variant="subtle" onClick={() => onTest(i)} aria-label="Test"><IconFlask size={16} /></ActionIcon>
              <ActionIcon variant="subtle" color="red" onClick={() => remove(i)} aria-label="Delete"><IconTrash size={16} /></ActionIcon>
            </Group>
          </Group>
        </Card>
      ))}
    </Stack>
  );
}
