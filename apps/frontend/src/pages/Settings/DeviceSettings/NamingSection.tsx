import { ActionIcon, Alert, Button, Group, Select, Stack, Switch, Table, TextInput, Title } from "@mantine/core";
import { IconTrash } from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
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

  const areas = useQuery({
    queryKey: ["areas"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/areas");
      if (error) throw new Error(String(error));
      return data ?? [];
    },
  });

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

  const overrideOptions: { value: string; label: string }[] = [
    ...(Object.keys(PRESET_LABELS) as Preset[]).map((v) => ({
      value: v, label: PRESET_LABELS[v],
    })),
    { value: "__disabled", label: "Disabled" },
  ];

  function updateOverride(i: number, patchObj: Record<string, unknown>) {
    const rooms = [...nc.rooms];
    rooms[i] = { ...rooms[i], ...patchObj };
    patch({ rooms });
  }

  function removeOverride(i: number) {
    const rooms = nc.rooms.filter((_: unknown, j: number) => j !== i);
    patch({ rooms });
  }

  function addOverride() {
    patch({ rooms: [...nc.rooms, { area_id: null, enabled: true, preset: "snake_case" }] });
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
      <Group justify="space-between">
        <Title order={5}>Per-Room Overrides</Title>
        <Button size="xs" onClick={addOverride}>+ Add Override</Button>
      </Group>
      {nc.rooms.length === 0 && (
        <Alert color="gray" variant="light">No room overrides yet.</Alert>
      )}
      {nc.rooms.length > 0 && (
        <Table withTableBorder>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Room</Table.Th>
              <Table.Th>Preset</Table.Th>
              <Table.Th>Pattern</Table.Th>
              <Table.Th>Starts With Room</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {nc.rooms.map((r: any, i: number) => {
              const presetValue = r.enabled ? (r.preset ?? "snake_case") : "__disabled";
              const areaOptions = (areas.data ?? []).map((a) => ({ value: a.id, label: a.name }));
              const orphanValue = r.area_id && !areaOptions.find((o) => o.value === r.area_id)
                ? r.area_id : null;
              return (
                <Table.Tr key={i}>
                  <Table.Td>
                    <Select
                      aria-label={`Room ${i}`}
                      searchable
                      data={orphanValue ? [...areaOptions, { value: orphanValue, label: `${orphanValue} (missing)` }] : areaOptions}
                      value={r.area_id ?? null}
                      onChange={(v) => updateOverride(i, { area_id: v })}
                    />
                  </Table.Td>
                  <Table.Td>
                    <Select
                      aria-label={`Preset for room ${i}`}
                      data={overrideOptions}
                      value={presetValue}
                      onChange={(v) => {
                        if (v === "__disabled") {
                          updateOverride(i, { enabled: false, preset: null, pattern: null, starts_with_room: null });
                        } else if (v === "custom") {
                          updateOverride(i, { enabled: true, preset: "custom", pattern: r.pattern ?? "" });
                        } else if (v) {
                          updateOverride(i, { enabled: true, preset: v, pattern: null });
                        }
                      }}
                    />
                  </Table.Td>
                  <Table.Td>
                    {r.enabled && r.preset === "custom" && (
                      <TextInput
                        value={r.pattern ?? ""}
                        onChange={(e) => updateOverride(i, { pattern: e.currentTarget.value })}
                      />
                    )}
                  </Table.Td>
                  <Table.Td>
                    {r.enabled && (
                      <Switch
                        aria-label={`Starts with room for row ${i}`}
                        checked={r.starts_with_room === null || r.starts_with_room === undefined
                          ? nc.starts_with_room : r.starts_with_room}
                        onChange={(e) => updateOverride(i, { starts_with_room: e.currentTarget.checked })}
                      />
                    )}
                  </Table.Td>
                  <Table.Td>
                    <ActionIcon variant="subtle" color="red" onClick={() => removeOverride(i)}>
                      <IconTrash size={16} />
                    </ActionIcon>
                  </Table.Td>
                </Table.Tr>
              );
            })}
          </Table.Tbody>
        </Table>
      )}
    </Stack>
  );
}
