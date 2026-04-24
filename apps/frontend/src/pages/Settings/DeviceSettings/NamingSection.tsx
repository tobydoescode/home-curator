import {
  ActionIcon,
  Alert,
  Button,
  Group,
  Select,
  Stack,
  Switch,
  Table,
  TextInput,
  Title,
} from "@mantine/core";
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

type Preset =
  | "snake_case"
  | "kebab-case"
  | "title-case"
  | "prefix-type-n"
  | "custom";

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

// ---------------------------------------------------------------------------
// Generic block editor. Does not know about the wrapping policy shape; edits
// only {preset, pattern, starts_with_room, rooms[]}. Shared by the device
// naming section and the Entity Settings page.
// ---------------------------------------------------------------------------
export interface NamingBlock {
  preset: Preset;
  pattern?: string | null;
  starts_with_room?: boolean;
  rooms?: RoomOverride[];
}

export interface NamingBlockSectionProps {
  block: NamingBlock;
  onBlockChange: (next: NamingBlock) => void;
  /** When false, the preset dropdown is hidden (entity_id shape). */
  showPreset?: boolean;
  /** When false, the custom-pattern field is hidden (entity_id shape). */
  allowCustomPattern?: boolean;
  /** Label for the starts-with-room switch. Entity-side callers override
   *  with verbose "starts with device name (or room if standalone)" wording
   *  since the semantics differ on the entity side. */
  startsWithRoomLabel?: string;
}

export function NamingBlockSection({
  block,
  onBlockChange,
  showPreset = true,
  allowCustomPattern = true,
  startsWithRoomLabel = "Starts with room name",
}: NamingBlockSectionProps) {
  const areas = useQuery({
    queryKey: ["areas"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/areas");
      if (error) throw new Error(String(error));
      return data ?? [];
    },
  });

  const rooms = block.rooms ?? [];
  const overrideOptions: { value: string; label: string }[] = [
    ...(Object.keys(PRESET_LABELS) as Preset[]).map((v) => ({
      value: v,
      label: PRESET_LABELS[v],
    })),
    { value: "__disabled", label: "Disabled" },
  ];

  function patchBlock(next: Partial<NamingBlock>): void {
    onBlockChange({ ...block, ...next });
  }

  function updateOverride(i: number, patchObj: Partial<RoomOverride>): void {
    const next = [...rooms];
    next[i] = { ...next[i], ...patchObj };
    patchBlock({ rooms: next });
  }

  function removeOverride(i: number): void {
    patchBlock({ rooms: rooms.filter((_, j) => j !== i) });
  }

  function addOverride(): void {
    patchBlock({
      rooms: [
        ...rooms,
        { area_id: null, enabled: true, preset: "snake_case" },
      ],
    });
  }

  return (
    <Stack>
      <Group align="flex-start">
        {showPreset && (
          <Select
            label="Preset"
            aria-label="Preset"
            data={(Object.keys(PRESET_LABELS) as Preset[]).map((v) => ({
              value: v,
              label: PRESET_LABELS[v],
            }))}
            value={block.preset}
            onChange={(v) => {
              if (!v) return;
              patchBlock({
                preset: v as Preset,
                pattern: v === "custom" ? "" : undefined,
              });
            }}
            description={`e.g. ${PRESET_EXAMPLE[block.preset]}`}
            inputWrapperOrder={["label", "input", "description", "error"]}
          />
        )}
        {allowCustomPattern && block.preset === "custom" && (
          <TextInput
            label="Pattern"
            aria-label="Pattern"
            value={block.pattern ?? ""}
            onChange={(e) => {
              const v = e.currentTarget.value;
              patchBlock({ pattern: v });
            }}
            style={{ flex: 1 }}
          />
        )}
      </Group>
      <Switch
        role="switch"
        aria-label={startsWithRoomLabel}
        label={startsWithRoomLabel}
        checked={!!block.starts_with_room}
        onChange={(e) => {
          const v = e.currentTarget.checked;
          patchBlock({ starts_with_room: v });
        }}
      />
      <Group justify="space-between">
        <Title order={5}>Per-Room Overrides</Title>
        <Button size="xs" onClick={addOverride}>
          + Add Override
        </Button>
      </Group>
      {rooms.length === 0 && (
        <Alert color="gray" variant="light">
          No room overrides yet.
        </Alert>
      )}
      {rooms.length > 0 && (
        <Table withTableBorder>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Room</Table.Th>
              {showPreset && <Table.Th>Preset</Table.Th>}
              {allowCustomPattern && <Table.Th>Pattern</Table.Th>}
              <Table.Th>Starts With Room</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {rooms.map((r, i) => {
              const presetValue = r.enabled
                ? r.preset ?? "snake_case"
                : "__disabled";
              const usedElsewhere = new Set(
                rooms
                  .filter((_, j) => j !== i)
                  .map((o) => o.area_id)
                  .filter((v): v is string => Boolean(v)),
              );
              const areaOptions = (areas.data ?? [])
                .filter((a) => !usedElsewhere.has(a.id))
                .map((a) => ({ value: a.id, label: a.name }));
              const orphanValue =
                r.area_id &&
                !areaOptions.find((o) => o.value === r.area_id)
                  ? r.area_id
                  : null;
              return (
                <Table.Tr key={i}>
                  <Table.Td>
                    <Select
                      aria-label={`Room ${i}`}
                      searchable
                      data={
                        orphanValue
                          ? [
                              ...areaOptions,
                              {
                                value: orphanValue,
                                label: `${orphanValue} (missing)`,
                              },
                            ]
                          : areaOptions
                      }
                      value={r.area_id ?? null}
                      onChange={(v) => updateOverride(i, { area_id: v })}
                    />
                  </Table.Td>
                  {showPreset && (
                    <Table.Td>
                      <Select
                        aria-label={`Preset for room ${i}`}
                        data={overrideOptions}
                        value={presetValue}
                        onChange={(v) => {
                          if (v === "__disabled") {
                            updateOverride(i, {
                              enabled: false,
                              preset: null,
                              pattern: null,
                              starts_with_room: null,
                            });
                          } else if (v === "custom") {
                            updateOverride(i, {
                              enabled: true,
                              preset: "custom",
                              pattern: r.pattern ?? "",
                            });
                          } else if (v) {
                            updateOverride(i, {
                              enabled: true,
                              preset: v as Preset,
                              pattern: null,
                            });
                          }
                        }}
                      />
                    </Table.Td>
                  )}
                  {allowCustomPattern && (
                    <Table.Td>
                      {r.enabled && r.preset === "custom" && (
                        <TextInput
                          value={r.pattern ?? ""}
                          onChange={(e) => {
                            const v = e.currentTarget.value;
                            updateOverride(i, { pattern: v });
                          }}
                        />
                      )}
                    </Table.Td>
                  )}
                  <Table.Td>
                    {r.enabled && (
                      <Switch
                        aria-label={`Starts with room for row ${i}`}
                        checked={
                          r.starts_with_room === null ||
                          r.starts_with_room === undefined
                            ? !!block.starts_with_room
                            : r.starts_with_room
                        }
                        onChange={(e) => {
                          const v = e.currentTarget.checked;
                          updateOverride(i, { starts_with_room: v });
                        }}
                      />
                    )}
                  </Table.Td>
                  <Table.Td>
                    <ActionIcon
                      variant="subtle"
                      color="red"
                      onClick={() => removeOverride(i)}
                    >
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

// ---------------------------------------------------------------------------
// Device-naming wrapper: preserves the original (draft, onChange) signature
// used by DeviceSettingsPage. Extracts the block, wires NamingBlockSection,
// and keeps severity + enabled alongside the block.
// ---------------------------------------------------------------------------
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
  const nc = draft.policies[idx] as NamingPolicy;

  function patchPolicy(next: Partial<NamingPolicy>): void {
    const policies = [...draft.policies];
    policies[idx] = { ...nc, ...next };
    onChange({ ...draft, policies });
  }

  const block: NamingBlock = {
    preset: nc.global.preset as Preset,
    pattern: nc.global.pattern ?? null,
    starts_with_room: !!nc.starts_with_room,
    rooms: nc.rooms ?? [],
  };

  function onBlockChange(next: NamingBlock): void {
    patchPolicy({
      global: { preset: next.preset, pattern: next.pattern ?? undefined },
      starts_with_room: !!next.starts_with_room,
      rooms: next.rooms ?? [],
    });
  }

  return (
    <Stack>
      <Title order={4}>Naming</Title>
      <Group>
        <Select
          label="Severity"
          aria-label="Severity"
          data={SEVERITIES.map((s) => ({
            value: s,
            label: s[0].toUpperCase() + s.slice(1),
          }))}
          value={nc.severity}
          onChange={(v) =>
            v && patchPolicy({ severity: v as NamingPolicy["severity"] })
          }
        />
        <Switch
          label="Enabled"
          checked={nc.enabled}
          onChange={(e) => {
            const v = e.currentTarget.checked;
            patchPolicy({ enabled: v });
          }}
          mt={28}
        />
      </Group>
      <NamingBlockSection block={block} onBlockChange={onBlockChange} />
    </Stack>
  );
}
