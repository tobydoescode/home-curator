import {
  Alert,
  Button,
  Checkbox,
  Code,
  Group,
  Stack,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { useState } from "react";

import {
  useRenameEntityPattern,
  type RenameEntityPatternBody,
} from "@/hooks/useEntityActions";

interface Props {
  entityIds: string[];
  onClose: () => void;
}

interface SectionState {
  enabled: boolean;
  pattern: string;
  replacement: string;
  invalid: boolean;
}

interface PreviewRow {
  entity_id: string;
  id_changed?: boolean;
  new_entity_id?: string | null;
  name_changed?: boolean;
  new_name?: string | null;
  ok: boolean;
  error?: string | null;
}

const PREVIEW_CAP = 100;

function validateRegex(pattern: string): boolean {
  if (!pattern) return false;
  try {
    new RegExp(pattern);
    return true;
  } catch {
    return false;
  }
}

export function RenameEntityPatternModal({ entityIds, onClose }: Props) {
  const [id, setId] = useState<SectionState>({
    enabled: true,
    pattern: "",
    replacement: "",
    invalid: false,
  });
  const [nm, setNm] = useState<SectionState>({
    enabled: true,
    pattern: "",
    replacement: "",
    invalid: false,
  });
  const [preview, setPreview] = useState<PreviewRow[] | null>(null);
  const mutation = useRenameEntityPattern();

  const idUsable = !id.enabled || !id.invalid;
  const nmUsable = !nm.enabled || !nm.invalid;
  const atLeastOneSection = id.enabled || nm.enabled;
  const canSubmit =
    atLeastOneSection && idUsable && nmUsable && !mutation.isPending;

  function buildBody(dry_run: boolean): RenameEntityPatternBody {
    const body: RenameEntityPatternBody = { entity_ids: entityIds, dry_run };
    if (id.enabled) {
      body.id_pattern = id.pattern;
      body.id_replacement = id.replacement;
    }
    if (nm.enabled) {
      body.name_pattern = nm.pattern;
      body.name_replacement = nm.replacement;
    }
    return body;
  }

  async function onDryRun() {
    const res = await mutation.mutateAsync(buildBody(true));
    setPreview(res.results as PreviewRow[]);
  }

  async function onApply() {
    await mutation.mutateAsync(buildBody(false));
    onClose();
  }

  const overflow = (preview?.length ?? 0) - PREVIEW_CAP;

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={5}>Entity ID</Title>
        <Checkbox
          label="Entity ID"
          aria-label="Entity ID"
          checked={id.enabled}
          onChange={(e) => {
            const v = e.currentTarget.checked;
            setId((s) => ({ ...s, enabled: v }));
          }}
        />
      </Group>
      {id.enabled && (
        <>
          <Alert color="yellow" variant="light">
            Renaming entity IDs can break references. Check automations,
            scripts, scenes, templates, Lovelace, and Spook afterwards.
          </Alert>
          <TextInput
            label="Pattern (Entity ID)"
            placeholder="^light\.office_(.+)$"
            value={id.pattern}
            onChange={(e) => {
              const v = e.currentTarget.value;
              setId((s) => ({ ...s, pattern: v, invalid: false }));
            }}
            onBlur={() =>
              setId((s) => ({ ...s, invalid: !validateRegex(s.pattern) }))
            }
            error={id.invalid ? "Invalid regex" : undefined}
          />
          <TextInput
            label="Replacement (Entity ID)"
            placeholder="light.study_$1"
            value={id.replacement}
            onChange={(e) => {
              const v = e.currentTarget.value;
              setId((s) => ({ ...s, replacement: v }));
            }}
          />
        </>
      )}

      <Group justify="space-between">
        <Title order={5}>Friendly Name</Title>
        <Checkbox
          label="Friendly Name"
          aria-label="Friendly Name"
          checked={nm.enabled}
          onChange={(e) => {
            const v = e.currentTarget.checked;
            setNm((s) => ({ ...s, enabled: v }));
          }}
        />
      </Group>
      {nm.enabled && (
        <>
          <TextInput
            label="Pattern (Friendly Name)"
            placeholder="^Office\s+(.+)$"
            value={nm.pattern}
            onChange={(e) => {
              const v = e.currentTarget.value;
              setNm((s) => ({ ...s, pattern: v, invalid: false }));
            }}
            onBlur={() =>
              setNm((s) => ({ ...s, invalid: !validateRegex(s.pattern) }))
            }
            error={nm.invalid ? "Invalid regex" : undefined}
          />
          <TextInput
            label="Replacement (Friendly Name)"
            placeholder="Study $1"
            value={nm.replacement}
            onChange={(e) => {
              const v = e.currentTarget.value;
              setNm((s) => ({ ...s, replacement: v }));
            }}
          />
        </>
      )}

      {preview && preview.length > 0 && (
        <Stack gap={4}>
          <Text size="sm" fw={500}>
            Preview ({preview.length}{" "}
            {preview.length === 1 ? "entity" : "entities"})
          </Text>
          {preview.slice(0, PREVIEW_CAP).map((r) => (
            <Stack key={r.entity_id} gap={0}>
              <Text size="xs">
                <Code>{r.entity_id}</Code>
                {r.id_changed && r.new_entity_id ? (
                  <>
                    {" → "}
                    <Code>{r.new_entity_id}</Code>
                  </>
                ) : null}
              </Text>
              {r.name_changed && r.new_name ? (
                <Text size="xs" c="dimmed">
                  {r.new_name}
                </Text>
              ) : null}
              {!r.ok && r.error ? (
                <Text size="xs" c="red">
                  {r.error}
                </Text>
              ) : null}
            </Stack>
          ))}
          {overflow > 0 && (
            <Text size="xs" c="dimmed">
              … ({overflow} more)
            </Text>
          )}
        </Stack>
      )}

      <Group justify="flex-end">
        <Button variant="subtle" onClick={onClose}>
          Cancel
        </Button>
        <Button variant="default" onClick={onDryRun} disabled={!canSubmit}>
          Dry Run
        </Button>
        <Button onClick={onApply} disabled={!canSubmit} loading={mutation.isPending}>
          Apply
        </Button>
      </Group>
    </Stack>
  );
}
