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
import { useNavigate } from "react-router-dom";

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

const SLUG_RE = /^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$/;

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
  const [slug, setSlug] = useState<string>(entity?.entity_id ?? "");
  const [name, setName] = useState<string>(entity?.name ?? "");
  const [areaId, setAreaId] = useState<string | null>(entity?.area_id ?? null);
  const [enabled, setEnabled] = useState<boolean>(entity?.disabled_by === null);
  const [visible, setVisible] = useState<boolean>(entity?.hidden_by === null);
  const [notes, setNotes] = useState<Record<string, string>>({});

  // Re-seed when the entity prop points at a different slug.
  useEffect(() => {
    if (!entity) return;
    setEditingId(entity.entity_id);
    setSlug(entity.entity_id);
    setName(entity.name ?? "");
    setAreaId(entity.area_id);
    setEnabled(entity.disabled_by === null);
    setVisible(entity.hidden_by === null);
    setNotes({});
  }, [entity?.entity_id]);

  if (!entity) return null;

  const initialName = entity.name ?? "";
  const slugValid = SLUG_RE.test(slug);
  const slugDirty = slug !== entity.entity_id;
  const nameDirty = name !== initialName;
  const areaDirty = areaId !== entity.area_id;
  const enabledDirty = enabled !== (entity.disabled_by === null);
  const visibleDirty = visible !== (entity.hidden_by === null);
  const isDirty =
    slugDirty || nameDirty || areaDirty || enabledDirty || visibleDirty;
  const canSave = isDirty && slugValid && !update.isPending;

  function buildChanges(): UpdateEntityChanges {
    const c: UpdateEntityChanges = {};
    if (slugDirty) c.new_entity_id = slug;
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
          if (slugDirty) setEditingId(slug);
        },
      },
    );
  };

  const save = () => {
    if (!canSave) return;
    if (slugDirty) {
      openRenameConfirmModal({
        oldId: entity.entity_id,
        newId: slug,
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
          value={slug}
          onChange={(e) => setSlug(e.currentTarget.value)}
          error={!slugValid ? "Invalid slug (expected domain.object_id)" : undefined}
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
