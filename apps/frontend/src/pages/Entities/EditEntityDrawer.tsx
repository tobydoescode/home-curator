import {
  Alert,
  Anchor,
  Button,
  Divider,
  Drawer,
  Group,
  Select,
  Stack,
  Switch,
  Text,
  TextInput,
  Textarea,
} from "@mantine/core";
import { modals } from "@mantine/modals";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router";

import { SeverityBadge } from "@/components/SeverityBadge";
import {
  useDeleteEntities,
  useUpdateEntity,
  type UpdateEntityChanges,
} from "@/hooks/useEntityActions";
import {
  useAcknowledgeException,
  useClearException,
} from "@/hooks/useExceptions";
import { openRenameConfirmModal } from "./modals/RenameConfirmModal";

// Domain (e.g. "light", "sensor") is baked into what kind of entity this is
// in HA. Changing it would usually be a mistake, so only the object_id part
// is editable in the drawer. Object_id must be snake_case.
const OBJECT_ID_RE = /^[a-z][a-z0-9_]*$/;

function splitEntityId(id: string): { domain: string; object: string } {
  const dot = id.indexOf(".");
  if (dot < 0) return { domain: "", object: id };
  return { domain: id.slice(0, dot), object: id.slice(dot + 1) };
}

export interface EditEntityDrawerEntity {
  entity_id: string;
  name: string | null;
  original_name: string | null;
  domain: string;
  platform: string;
  device_id: string | null;
  device_name: string | null;
  area_id: string | null;
  area_name: string | null;
  disabled_by: string | null;
  hidden_by: string | null;
  icon: string | null;
  issues: Array<{
    policy_id: string;
    rule_type: string;
    severity: "info" | "warning" | "error";
    message: string;
  }>;
}

interface Props {
  opened: boolean;
  onClose: () => void;
  entity: EditEntityDrawerEntity | null;
  areas: { id: string; name: string }[];
}

export function EditEntityDrawer({ opened, onClose, entity, areas }: Props) {
  const navigate = useNavigate();
  const update = useUpdateEntity();
  const deleteEntities = useDeleteEntities();
  const ack = useAcknowledgeException();
  const clear = useClearException();

  // Track the "identity" of the entity we're editing — shifts after a
  // successful rename so subsequent saves PATCH the new slug.
  const [editingId, setEditingId] = useState<string>(entity?.entity_id ?? "");
  const initialDomain = entity ? splitEntityId(entity.entity_id).domain : "";
  const initialObject = entity ? splitEntityId(entity.entity_id).object : "";
  const [objectId, setObjectId] = useState<string>(initialObject);
  const [name, setName] = useState<string>(entity?.name ?? "");
  const [areaId, setAreaId] = useState<string | null>(entity?.area_id ?? null);
  const [enabled, setEnabled] = useState<boolean>(entity?.disabled_by === null);
  const [visible, setVisible] = useState<boolean>(entity?.hidden_by === null);
  const [notes, setNotes] = useState<Record<string, string>>({});

  // Re-seed when the entity prop points at a different slug.
  useEffect(() => {
    if (!entity) return;
    setEditingId(entity.entity_id);
    setObjectId(splitEntityId(entity.entity_id).object);
    setName(entity.name ?? "");
    setAreaId(entity.area_id);
    setEnabled(entity.disabled_by === null);
    setVisible(entity.hidden_by === null);
    setNotes({});
  }, [entity?.entity_id]);

  if (!entity) return null;

  const initialName = entity.name ?? "";
  const objectIdValid = OBJECT_ID_RE.test(objectId);
  const newSlug = `${initialDomain}.${objectId}`;
  const slugDirty = newSlug !== entity.entity_id;
  const nameDirty = name !== initialName;
  const areaDirty = areaId !== entity.area_id;
  const enabledDirty = enabled !== (entity.disabled_by === null);
  const visibleDirty = visible !== (entity.hidden_by === null);
  const isDirty =
    slugDirty || nameDirty || areaDirty || enabledDirty || visibleDirty;
  const canSave = isDirty && objectIdValid && !update.isPending;

  function buildChanges(): UpdateEntityChanges {
    const c: UpdateEntityChanges = {};
    if (slugDirty) c.new_entity_id = newSlug;
    if (nameDirty) c.name = name === "" ? null : name;
    if (areaDirty) c.area_id = areaId;
    if (enabledDirty) c.disabled_by = enabled ? null : "user";
    if (visibleDirty) c.hidden_by = visible ? null : "user";
    return c;
  }

  const doSave = () => {
    const changes = buildChanges();
    update.mutate(
      { entity_id: editingId, changes },
      {
        onSuccess: () => {
          if (slugDirty) setEditingId(newSlug);
        },
      },
    );
  };

  const save = () => {
    if (!canSave) return;
    if (slugDirty) {
      openRenameConfirmModal({
        oldId: entity.entity_id,
        newId: newSlug,
        onConfirm: doSave,
      });
      return;
    }
    doSave();
  };

  const displayName = name || entity.original_name || entity.entity_id;
  // Delete confirms the entity's identity, not the pending edits — so use the
  // entity prop's display name even if the Name field has unsaved edits.
  const deleteName = entity.name || entity.original_name || entity.entity_id;

  const openDelete = () => {
    modals.openConfirmModal({
      title: `Delete ${deleteName}?`,
      children:
        "This cannot be undone. If the integration refuses, the entity will stay.",
      labels: { confirm: "Delete", cancel: "Keep" },
      confirmProps: { color: "red" },
      onConfirm: () => {
        deleteEntities.mutate([editingId], {
          onSuccess: (res) => {
            if (res.results[0]?.ok) onClose();
          },
        });
      },
    });
  };

  const requestClose = () => {
    if (!isDirty) {
      onClose();
      return;
    }
    modals.openConfirmModal({
      title: "Discard changes?",
      children: "You have unsaved changes on this entity.",
      labels: { confirm: "Discard", cancel: "Keep editing" },
      confirmProps: { color: "red" },
      onConfirm: onClose,
    });
  };

  return (
    <Drawer
      opened={opened}
      onClose={requestClose}
      title={displayName}
      position="right"
      size="lg"
    >
      <Stack>
        <Alert color="yellow" variant="light">
          Renaming the entity ID can break references. Check these places
          after saving: Automations, Scripts, Scenes, Templates, Lovelace
          dashboards, External integrations (e.g. Spook).
        </Alert>
        <TextInput
          label="Entity ID"
          // Domain is readonly — changing it would repurpose the entity's
          // type (e.g. light→switch) which is almost always a mistake.
          // Show it as a dimmed leftSection so the user still sees the full
          // slug but can only edit the object_id portion.
          leftSection={
            <Text size="sm" c="dimmed" pl={4}>
              {initialDomain}.
            </Text>
          }
          leftSectionWidth={`calc(${initialDomain.length}ch + 1.25rem)`}
          value={objectId}
          onChange={(e) => setObjectId(e.currentTarget.value)}
          error={
            !objectIdValid
              ? "Invalid object ID (lowercase letters, digits, underscores)"
              : undefined
          }
        />
        <TextInput
          label="Name"
          placeholder={entity.original_name ?? ""}
          value={name}
          onChange={(e) => setName(e.currentTarget.value)}
        />
        <Group grow>
          <TextInput label="Domain" value={entity.domain} readOnly />
          <TextInput label="Platform" value={entity.platform} readOnly />
        </Group>
        <Select
          label="Room"
          data={areas.map((a) => ({ value: a.id, label: a.name }))}
          value={areaId}
          onChange={setAreaId}
          searchable
          clearable
        />
        <Text size="sm">
          Device:{" "}
          {entity.device_id && entity.device_name ? (
            <Anchor
              component="button"
              type="button"
              onClick={() => navigate(`/devices?device=${entity.device_id}`)}
            >
              {entity.device_name}
            </Anchor>
          ) : (
            <Text span c="dimmed">
              —
            </Text>
          )}
        </Text>
        <Group>
          <Switch
            label="Enabled"
            checked={enabled}
            onChange={(e) => setEnabled(e.currentTarget.checked)}
          />
          <Switch
            label="Visible"
            checked={visible}
            onChange={(e) => setVisible(e.currentTarget.checked)}
          />
        </Group>
        <Group justify="space-between">
          <Button
            color="red"
            variant="light"
            onClick={openDelete}
            loading={deleteEntities.isPending}
          >
            Delete
          </Button>
          <Group gap="xs">
            <Button variant="subtle" onClick={requestClose}>
              Cancel
            </Button>
            <Button disabled={!canSave} onClick={save} loading={update.isPending}>
              Save
            </Button>
          </Group>
        </Group>
        {entity.issues.length > 0 && <Divider my="sm" />}
        {entity.issues.length > 0 && (
          <Stack gap="md">
            {entity.issues.map((issue) => (
              <Stack key={issue.policy_id} gap="xs">
                <Group>
                  <SeverityBadge severity={issue.severity} count={1} />
                  <Text fw={500}>{issue.message}</Text>
                </Group>
                <Text size="xs" c="dimmed">
                  Rule: {issue.rule_type} · Policy: {issue.policy_id}
                </Text>
                <Textarea
                  placeholder="Optional Note"
                  value={notes[issue.policy_id] ?? ""}
                  onChange={(e) => {
                    const value = e.currentTarget.value;
                    setNotes((n) => ({ ...n, [issue.policy_id]: value }));
                  }}
                />
                <Group gap="xs">
                  <Button
                    size="xs"
                    onClick={() =>
                      ack.mutate({
                        entity_id: editingId,
                        policy_id: issue.policy_id,
                        note: notes[issue.policy_id],
                      })
                    }
                    loading={ack.isPending}
                  >
                    Acknowledge As Exception
                  </Button>
                  <Button
                    size="xs"
                    variant="subtle"
                    loading={clear.isPending}
                    onClick={() =>
                      clear.mutate({
                        entity_id: editingId,
                        policy_id: issue.policy_id,
                      })
                    }
                  >
                    Clear Exception
                  </Button>
                </Group>
              </Stack>
            ))}
          </Stack>
        )}
      </Stack>
    </Drawer>
  );
}
