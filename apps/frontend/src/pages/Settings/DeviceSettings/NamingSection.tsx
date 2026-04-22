import { Group, Select, Stack, Switch, TextInput, Title } from "@mantine/core";

import type { PoliciesFileShape } from "@/hooks/usePolicies";

export interface SectionProps {
  draft: PoliciesFileShape;
  onChange: (d: PoliciesFileShape) => void;
}

type Preset = "snake_case" | "kebab-case" | "title-case" | "prefix-type-n" | "custom";

const PRESET_LABELS: Record<Preset, string> = {
  snake_case: "snake_case",
  "kebab-case": "kebab-case",
  "title-case": "Title Case",
  "prefix-type-n": "Prefix + Type + N",
  custom: "Custom Regex",
};

const PRESET_EXAMPLE: Record<Preset, string> = {
  snake_case: "kitchen_light_1",
  "kebab-case": "kitchen-light-1",
  "title-case": "Kitchen Light 1",
  "prefix-type-n": "kt_light_1",
  custom: "Your own pattern",
};

const SEVERITIES = ["info", "warning", "error"] as const;

export function NamingSection({ draft, onChange }: SectionProps) {
  const idx = draft.policies.findIndex((p) => p.type === "naming_convention");
  if (idx < 0) {
    return (
      <Stack>
        <Title order={4}>Naming</Title>
        <div>No naming policy defined.</div>
      </Stack>
    );
  }
  const nc = draft.policies[idx] as any;

  function patch(next: Record<string, unknown>) {
    const policies = [...draft.policies];
    policies[idx] = { ...nc, ...next };
    onChange({ ...draft, policies });
  }

  return (
    <Stack>
      <Title order={4}>Naming</Title>
      <Group align="flex-end">
        <Select
          label="Preset"
          aria-label="Preset"
          data={(Object.keys(PRESET_LABELS) as Preset[]).map((v) => ({
            value: v, label: PRESET_LABELS[v],
          }))}
          value={nc.global.preset}
          onChange={(v) => {
            if (!v) return;
            patch({
              global: {
                preset: v,
                pattern: v === "custom" ? "" : undefined,
              },
            });
          }}
          description={`e.g. ${PRESET_EXAMPLE[nc.global.preset as Preset]}`}
        />
        {nc.global.preset === "custom" && (
          <TextInput
            label="Pattern"
            aria-label="Pattern"
            value={nc.global.pattern ?? ""}
            onChange={(e) => patch({ global: { ...nc.global, pattern: e.currentTarget.value } })}
            style={{ flex: 1 }}
          />
        )}
        <Select
          label="Severity"
          aria-label="Severity"
          data={SEVERITIES.map((s) => ({ value: s, label: s[0].toUpperCase() + s.slice(1) }))}
          value={nc.severity}
          onChange={(v) => v && patch({ severity: v })}
        />
        <Switch
          label="Enabled"
          checked={nc.enabled}
          onChange={(e) => patch({ enabled: e.currentTarget.checked })}
        />
      </Group>
      <Switch
        role="switch"
        aria-label="Starts with room name"
        label="Starts with room name"
        checked={!!nc.starts_with_room}
        onChange={(e) => patch({ starts_with_room: e.currentTarget.checked })}
      />
    </Stack>
  );
}
