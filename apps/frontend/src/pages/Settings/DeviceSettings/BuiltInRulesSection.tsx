import { Card, Group, Select, Stack, Switch, Text, Title } from "@mantine/core";

import type { components } from "@/api/generated";
import type { SectionProps } from "./NamingSection";

type Severity = components["schemas"]["MissingAreaPolicy"]["severity"];
// Every canned built-in rule shares the same `id / type / enabled / severity`
// surface — pick any as the shape we need for rendering.
type BuiltInLike = components["schemas"]["MissingAreaPolicy"];

const BUILT_INS: Record<string, { title: string; explanation: string }> = {
  missing_area: {
    title: "Missing Room",
    explanation: "Flags devices with no assigned area.",
  },
  reappeared_after_delete: {
    title: "Reappeared After Delete",
    explanation: "Flags devices that were deleted in HA and later came back (tracked by stable identifier).",
  },
};

const SEVERITIES = ["info", "warning", "error"] as const;

export function BuiltInRulesSection({ draft, onChange }: SectionProps) {
  function patch(i: number, next: Partial<BuiltInLike>) {
    const policies = [...draft.policies];
    policies[i] = { ...policies[i], ...next } as typeof policies[number];
    onChange({ ...draft, policies });
  }

  const rows = draft.policies
    .map((p, i) => ({ p, i }))
    .filter(({ p }) => p.type in BUILT_INS) as { p: BuiltInLike; i: number }[];

  return (
    <Stack>
      <Title order={4}>Built-In Rules</Title>
      {rows.length === 0 && <Text c="dimmed">No built-in rules configured.</Text>}
      {rows.map(({ p, i }) => {
        const meta = BUILT_INS[p.type];
        return (
          <Card key={p.id} withBorder padding="sm">
            <Group justify="space-between" align="flex-start">
              <Stack gap={2}>
                <Title order={5}>{meta.title}</Title>
                <Text size="sm" c="dimmed">{meta.explanation}</Text>
              </Stack>
              <Group>
                <Select
                  aria-label={`Severity for ${meta.title}`}
                  data={SEVERITIES.map((s) => ({ value: s, label: s[0].toUpperCase() + s.slice(1) }))}
                  value={p.severity}
                  onChange={(v) => v && patch(i, { severity: v as Severity })}
                  w={120}
                />
                <Switch
                  aria-label={`Enable ${meta.title}`}
                  checked={p.enabled}
                  onChange={(e) => patch(i, { enabled: e.currentTarget.checked })}
                />
              </Group>
            </Group>
          </Card>
        );
      })}
    </Stack>
  );
}
