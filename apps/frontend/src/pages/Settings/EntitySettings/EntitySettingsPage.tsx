import {
  Accordion,
  Alert,
  Button,
  Card,
  Group,
  Loader,
  Select,
  Stack,
  Switch,
  Text,
  Title,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useEffect, useState } from "react";

import { CustomRulesSection } from "@/pages/Settings/DeviceSettings/CustomRulesSection";
import {
  NamingBlockSection,
  type NamingBlock,
} from "@/pages/Settings/DeviceSettings/NamingSection";
import {
  usePoliciesFile,
  useUpdatePolicies,
  type PoliciesFileShape,
} from "@/hooks/usePolicies";

import {
  EntityIdNamingSection,
  type EntityIdBlock,
} from "./EntityIdNamingSection";

const SEVERITIES = ["info", "warning", "error"] as const;

export function EntitySettingsPage() {
  const { data, isLoading, error } = usePoliciesFile();
  const update = useUpdatePolicies();
  const [draft, setDraft] = useState<PoliciesFileShape | null>(null);

  useEffect(() => {
    if (data) setDraft(structuredClone(data));
  }, [data]);

  if (isLoading || draft === null) return <Loader />;
  if (error)
    return (
      <Alert color="red" title="Failed To Load Policies">
        {String(error)}
      </Alert>
    );

  const namingIdx = draft.policies.findIndex(
    (p) => p.type === "entity_naming_convention",
  );
  const missingAreaIdx = draft.policies.findIndex(
    (p) => p.type === "entity_missing_area",
  );
  const reappearedIdx = draft.policies.findIndex(
    (p) =>
      p.type === "reappeared_after_delete" &&
      (p as { scope?: string }).scope === "entities",
  );

  function patchPolicy(i: number, next: Record<string, unknown>): void {
    if (!draft || i < 0) return;
    const policies = [...draft.policies];
    policies[i] = { ...policies[i], ...next } as (typeof policies)[number];
    setDraft({ ...draft, policies });
  }

  async function save(): Promise<void> {
    if (!draft) return;
    try {
      await update.mutateAsync(draft);
      notifications.show({
        color: "green",
        title: "Saved",
        message: "Entity settings updated.",
      });
    } catch (e) {
      notifications.show({
        color: "red",
        title: "Save Failed",
        message: String(e),
      });
    }
  }

  const naming =
    namingIdx >= 0
      ? (draft.policies[namingIdx] as Record<string, unknown>)
      : null;
  const nameBlock: NamingBlock =
    (naming?.name as NamingBlock | undefined) ?? { preset: "title-case" };
  const idBlock: EntityIdBlock =
    (naming?.entity_id as EntityIdBlock | undefined) ?? {
      starts_with_room: false,
      rooms: [],
    };

  function onNameBlockChange(next: NamingBlock): void {
    patchPolicy(namingIdx, { name: next });
  }
  function onIdBlockChange(next: EntityIdBlock): void {
    patchPolicy(namingIdx, { entity_id: next });
  }

  return (
    <Stack gap="lg">
      <Title order={3}>Entity Settings</Title>

      {naming && (
        <Stack>
          <Title order={4}>Naming</Title>
          <Group>
            <Select
              label="Severity"
              data={SEVERITIES.map((s) => ({
                value: s,
                label: s[0].toUpperCase() + s.slice(1),
              }))}
              value={naming.severity as string}
              onChange={(v) => v && patchPolicy(namingIdx, { severity: v })}
            />
            <Switch
              label="Enabled"
              checked={Boolean(naming.enabled)}
              onChange={(e) => {
                const v = e.currentTarget.checked;
                patchPolicy(namingIdx, { enabled: v });
              }}
              mt={28}
            />
          </Group>
          <Accordion
            multiple
            defaultValue={["name", "entity_id"]}
            variant="separated"
          >
            <Accordion.Item value="name">
              <Accordion.Control>
                <Title order={5}>Friendly Name</Title>
              </Accordion.Control>
              <Accordion.Panel>
                <NamingBlockSection
                  block={nameBlock}
                  onBlockChange={onNameBlockChange}
                />
              </Accordion.Panel>
            </Accordion.Item>
            <Accordion.Item value="entity_id">
              <Accordion.Control>
                <Title order={5}>Entity ID</Title>
              </Accordion.Control>
              <Accordion.Panel>
                <EntityIdNamingSection
                  block={idBlock}
                  onChange={onIdBlockChange}
                />
              </Accordion.Panel>
            </Accordion.Item>
          </Accordion>
        </Stack>
      )}

      <Stack>
        <Title order={4}>Built-In Rules</Title>
        {missingAreaIdx >= 0 && (
          <Card withBorder padding="sm">
            <Group justify="space-between" align="flex-start">
              <Stack gap={2}>
                <Title order={5}>Entity Missing Area</Title>
                <Text size="sm" c="dimmed">
                  Flags entities that have no area assigned. Use{" "}
                  <em>Require own area</em> to require an override on the
                  entity itself instead of falling back to its owning
                  device's area.
                </Text>
              </Stack>
              <Group>
                <Select
                  aria-label="Severity for Entity Missing Area"
                  data={SEVERITIES.map((s) => ({
                    value: s,
                    label: s[0].toUpperCase() + s.slice(1),
                  }))}
                  value={
                    (
                      draft.policies[missingAreaIdx] as {
                        severity: string;
                      }
                    ).severity
                  }
                  onChange={(v) => v && patchPolicy(missingAreaIdx, { severity: v })}
                  w={120}
                />
                <Switch
                  aria-label="Enable Entity Missing Area"
                  checked={
                    (draft.policies[missingAreaIdx] as { enabled: boolean })
                      .enabled
                  }
                  onChange={(e) => {
                    const v = e.currentTarget.checked;
                    patchPolicy(missingAreaIdx, { enabled: v });
                  }}
                />
                <Switch
                  aria-label="Require Own Area"
                  label="Require Own Area"
                  checked={Boolean(
                    (draft.policies[missingAreaIdx] as {
                      require_own_area?: boolean;
                    }).require_own_area,
                  )}
                  onChange={(e) => {
                    const v = e.currentTarget.checked;
                    patchPolicy(missingAreaIdx, { require_own_area: v });
                  }}
                />
              </Group>
            </Group>
          </Card>
        )}
        {reappearedIdx >= 0 && (
          <Card withBorder padding="sm">
            <Group justify="space-between" align="flex-start">
              <Stack gap={2}>
                <Title order={5}>Entity Reappeared After Delete</Title>
                <Text size="sm" c="dimmed">
                  Flags entities that were deleted in HA and later came back
                  (tracked by stable identifier).
                </Text>
              </Stack>
              <Group>
                <Select
                  aria-label="Severity for Entity Reappeared After Delete"
                  data={SEVERITIES.map((s) => ({
                    value: s,
                    label: s[0].toUpperCase() + s.slice(1),
                  }))}
                  value={
                    (draft.policies[reappearedIdx] as { severity: string })
                      .severity
                  }
                  onChange={(v) => v && patchPolicy(reappearedIdx, { severity: v })}
                  w={120}
                />
                <Switch
                  aria-label="Enable Entity Reappeared After Delete"
                  checked={
                    (draft.policies[reappearedIdx] as { enabled: boolean })
                      .enabled
                  }
                  onChange={(e) => {
                    const v = e.currentTarget.checked;
                    patchPolicy(reappearedIdx, { enabled: v });
                  }}
                />
              </Group>
            </Group>
          </Card>
        )}
      </Stack>

      <CustomRulesSection draft={draft} onChange={setDraft} scope="entities" />

      <Group justify="flex-end">
        <Button onClick={save} loading={update.isPending}>
          Save
        </Button>
      </Group>
    </Stack>
  );
}
