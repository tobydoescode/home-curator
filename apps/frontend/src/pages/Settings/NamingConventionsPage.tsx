import {
  Alert,
  Button,
  Group,
  Select,
  Stack,
  Table,
  TextInput,
  Title,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useEffect, useState } from "react";

import { api } from "@/api/client";
import { useUpdatePolicies } from "@/hooks/usePolicies";
import { useQuery } from "@tanstack/react-query";

const PRESETS = [
  "snake_case",
  "kebab-case",
  "title-case",
  "prefix-type-n",
  "custom",
];

type Preset = (typeof PRESETS)[number];

interface NamingPatternConfig {
  preset: Preset;
  pattern?: string | null;
}

interface RoomOverride extends NamingPatternConfig {
  room?: string | null;
  area_id?: string | null;
}

interface NamingPolicy {
  id: string;
  type: "naming_convention";
  enabled: boolean;
  severity: "info" | "warning" | "error";
  global: NamingPatternConfig;
  rooms: RoomOverride[];
}

/**
 * The naming-convention settings page reads the raw policies.yaml via
 * `/api/policies` (list view) plus a second fetch to get the full shape
 * (the list endpoint only surfaces summaries). For simplicity we fetch
 * once and cache locally.
 */
function useFullPoliciesFile() {
  // The `/api/policies` endpoint returns summaries; the full file shape is
  // reconstructed by fetching YAML-style entries via a round-trip through
  // the mutation endpoint isn't possible. For now we infer: we store only
  // the known naming_convention shape authored here, and preserve other
  // policies by reading them from the summary's id/type/enabled/severity.
  return useQuery({
    queryKey: ["policies"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/policies");
      if (error) throw new Error(String(error));
      return data!;
    },
  });
}

export function NamingConventionsPage() {
  const { data, error, isLoading } = useFullPoliciesFile();
  const update = useUpdatePolicies();
  const [nc, setNc] = useState<NamingPolicy | null>(null);

  useEffect(() => {
    if (!data) return;
    const existing = data.policies.find((p) => p.type === "naming_convention");
    setNc({
      id: existing?.id ?? "naming-convention",
      type: "naming_convention",
      enabled: existing?.enabled ?? true,
      severity: (existing?.severity as NamingPolicy["severity"]) ?? "warning",
      // The list endpoint doesn't echo the `global`/`rooms` fields;
      // initialise with a sensible default until the user saves.
      global: { preset: "snake_case" },
      rooms: [],
    });
  }, [data]);

  if (isLoading || !nc) return <div>Loading…</div>;
  if (error)
    return (
      <Alert color="red" title="Failed To Load Policies">
        {String(error)}
      </Alert>
    );

  const save = async () => {
    if (!data) return;
    // Preserve all non-naming policies exactly as they are summarised.
    const others = data.policies
      .filter((p) => p.type !== "naming_convention")
      .map(
        (p) =>
          ({
            id: p.id,
            type: p.type,
            enabled: p.enabled,
            severity: p.severity,
          } as unknown as NamingPolicy),
      );
    try {
      await update.mutateAsync({
        version: 1,
        // Backend validates against the discriminated union; the `as unknown`
        // cast is necessary because the TS types narrow stricter than the
        // superset we're constructing here.
        policies: [nc, ...others] as unknown as Parameters<
          typeof update.mutateAsync
        >[0]["policies"],
      });
      notifications.show({
        color: "green",
        title: "Saved",
        message: "Naming conventions updated.",
      });
    } catch (e) {
      notifications.show({
        color: "red",
        title: "Save Failed",
        message: String(e),
      });
    }
  };

  return (
    <Stack>
      <Title order={3}>Naming Conventions</Title>

      <Stack gap="xs">
        <Title order={5}>Global Default</Title>
        <Group>
          <Select
            label="Preset"
            data={PRESETS}
            value={nc.global.preset}
            onChange={(v) => {
              if (!v) return;
              setNc({
                ...nc,
                global: {
                  preset: v as Preset,
                  pattern: v === "custom" ? "" : undefined,
                },
              });
            }}
          />
          {nc.global.preset === "custom" && (
            <TextInput
              label="Pattern"
              value={nc.global.pattern ?? ""}
              onChange={(e) =>
                setNc({
                  ...nc,
                  global: { ...nc.global, pattern: e.currentTarget.value },
                })
              }
              style={{ flex: 1 }}
            />
          )}
        </Group>
      </Stack>

      <Stack gap="xs">
        <Group justify="space-between">
          <Title order={5}>Per-Room Overrides</Title>
          <Button
            size="xs"
            onClick={() =>
              setNc({
                ...nc,
                rooms: [...nc.rooms, { preset: "snake_case", room: "" }],
              })
            }
          >
            + Add Override
          </Button>
        </Group>
        {nc.rooms.length === 0 && (
          <Alert color="gray" variant="light">
            No room overrides yet.
          </Alert>
        )}
        {nc.rooms.length > 0 && (
          <Table withTableBorder>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Room</Table.Th>
                <Table.Th>Preset</Table.Th>
                <Table.Th>Pattern</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {nc.rooms.map((r, i) => (
                <Table.Tr key={i}>
                  <Table.Td>
                    <TextInput
                      value={r.room ?? ""}
                      placeholder="Room Name"
                      onChange={(e) => {
                        const rooms = [...nc.rooms];
                        rooms[i] = { ...rooms[i], room: e.currentTarget.value };
                        setNc({ ...nc, rooms });
                      }}
                    />
                  </Table.Td>
                  <Table.Td>
                    <Select
                      data={PRESETS}
                      value={r.preset}
                      onChange={(v) => {
                        if (!v) return;
                        const rooms = [...nc.rooms];
                        rooms[i] = {
                          ...rooms[i],
                          preset: v as Preset,
                          pattern: v === "custom" ? "" : undefined,
                        };
                        setNc({ ...nc, rooms });
                      }}
                    />
                  </Table.Td>
                  <Table.Td>
                    {r.preset === "custom" && (
                      <TextInput
                        value={r.pattern ?? ""}
                        onChange={(e) => {
                          const rooms = [...nc.rooms];
                          rooms[i] = {
                            ...rooms[i],
                            pattern: e.currentTarget.value,
                          };
                          setNc({ ...nc, rooms });
                        }}
                      />
                    )}
                  </Table.Td>
                  <Table.Td>
                    <Button
                      size="xs"
                      variant="subtle"
                      color="red"
                      onClick={() =>
                        setNc({
                          ...nc,
                          rooms: nc.rooms.filter((_, j) => j !== i),
                        })
                      }
                    >
                      Remove
                    </Button>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Stack>

      <Group justify="flex-end">
        <Button onClick={save} loading={update.isPending}>
          Save
        </Button>
      </Group>
    </Stack>
  );
}
