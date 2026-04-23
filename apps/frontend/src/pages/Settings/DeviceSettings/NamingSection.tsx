import { ActionIcon, Alert, Button, Group, Select, Stack, Switch, Table, TextInput, Title } from "@mantine/core";
import { IconTrash } from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import type { components } from "@/api/generated";
import type { PoliciesFileShape } from "@/hooks/usePolicies";

type NamingPolicy = components["schemas"]["NamingConventionPolicy"];
type RoomOverride = components["schemas"]["RoomOverride"];

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
  const nc = draft.policies[idx] as NamingPolicy;
  // The generated schema types `rooms` as optional; normalise to an array
  // at the top so every downstream access can assume present.
  const rooms: RoomOverride[] = nc.rooms ?? [];

  function patch(next: Partial<NamingPolicy>) {
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

  function updateOverride(i: number, patchObj: Partial<RoomOverride>) {
    const next = [...rooms];
    next[i] = { ...next[i], ...patchObj };
    patch({ rooms: next });
  }

  function removeOverride(i: number) {
    patch({ rooms: rooms.filter((_, j) => j !== i) });
  }

  function addOverride() {
    patch({ rooms: [...rooms, { area_id: null, enabled: true, preset: "snake_case" }] });
  }

  return (
    <Stack>
      <Title order={4}>Naming</Title>
      <Group align="flex-start">
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
                preset: v as Preset,
                pattern: v === "custom" ? "" : undefined,
              },
            });
          }}
          description={`e.g. ${PRESET_EXAMPLE[nc.global.preset as Preset]}`}
          inputWrapperOrder={["label", "input", "description", "error"]}
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
          onChange={(v) => v && patch({ severity: v as NamingPolicy["severity"] })}
        />
        <Switch
          label="Enabled"
          checked={nc.enabled}
          onChange={(e) => patch({ enabled: e.currentTarget.checked })}
          mt={28}
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
      {rooms.length === 0 && (
        <Alert color="gray" variant="light">No room overrides yet.</Alert>
      )}
      {rooms.length > 0 && (
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
            {rooms.map((r, i) => {
              const presetValue = r.enabled ? (r.preset ?? "snake_case") : "__disabled";
              // Exclude area_ids already claimed by OTHER override rows so
              // the user can't pick the same room twice. The evaluator keys
              // by area_id, so duplicates would silently shadow each other.
              const usedElsewhere = new Set(
                rooms
                  .filter((_, j) => j !== i)
                  .map((o) => o.area_id)
                  .filter((v): v is string => Boolean(v)),
              );
              const areaOptions = (areas.data ?? [])
                .filter((a) => !usedElsewhere.has(a.id))
                .map((a) => ({ value: a.id, label: a.name }));
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
                          updateOverride(i, { enabled: true, preset: v as Preset, pattern: null });
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
