import { notifications } from "@mantine/notifications";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "@/api/client";

function invalidateEntities(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: ["entities"] });
}

export function useAssignRoomEntities() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { entity_ids: string[]; area_id: string }) => {
      const { data, error } = await api.POST(
        "/api/actions/assign-room-entities",
        { body },
      );
      if (error) throw new Error(String(error));
      return data!;
    },
    onSuccess: (res) => {
      const total = res.results.length;
      const failed = res.results.filter((r) => !r.ok).length;
      const ok = total - failed;
      notifications.show({
        title: failed === 0 ? "Room Assigned" : "Partial Update",
        message: failed
          ? `${ok} Updated, ${failed} Failed`
          : `${ok} Updated`,
        color: failed ? "yellow" : "green",
      });
      invalidateEntities(qc);
    },
    onError: (err) => {
      notifications.show({
        title: "Assign Room Failed",
        message: err instanceof Error ? err.message : "Unknown error",
        color: "red",
      });
    },
  });
}

type StateField = "disabled_by" | "hidden_by";
type StateValue = "user" | null;

interface StateCopy {
  // Keys: `${field}|${value === null ? "null" : "user"}`
  title: { single: string; many: string };
  verb: string;  // e.g. "Disabled", "Enabled"
}

const STATE_COPY: Record<string, StateCopy> = {
  "disabled_by|user": {
    title: { single: "Entity Disabled", many: "Entities Disabled" },
    verb: "Disabled",
  },
  "disabled_by|null": {
    title: { single: "Entity Enabled", many: "Entities Enabled" },
    verb: "Enabled",
  },
  "hidden_by|user": {
    title: { single: "Entity Hidden", many: "Entities Hidden" },
    verb: "Hidden",
  },
  "hidden_by|null": {
    title: { single: "Entity Shown", many: "Entities Shown" },
    verb: "Shown",
  },
};

export function useEntityState() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: {
      entity_ids: string[];
      field: StateField;
      value: StateValue;
    }) => {
      const { data, error } = await api.POST("/api/actions/entity-state", {
        body,
      });
      if (error) throw new Error(String(error));
      return data!;
    },
    onSuccess: (res, vars) => {
      const total = res.results.length;
      const failed = res.results.filter((r) => !r.ok).length;
      const ok = total - failed;
      const copy =
        STATE_COPY[`${vars.field}|${vars.value === null ? "null" : "user"}`];
      const title = total === 1 ? copy.title.single : copy.title.many;
      if (failed === 0) {
        notifications.show({
          title,
          message: `${ok} ${copy.verb}`,
          color: "green",
        });
      } else if (ok === 0) {
        const firstError = res.results.find((r) => r.error)?.error;
        notifications.show({
          title: `${title} Failed`,
          message:
            total === 1 ? firstError ?? "Unknown error" : `${failed} Failed`,
          color: "red",
        });
      } else {
        notifications.show({
          title: "Partial Update",
          message: `${ok} ${copy.verb}, ${failed} Failed`,
          color: "yellow",
        });
      }
      invalidateEntities(qc);
    },
    onError: (err) => {
      notifications.show({
        title: "Update Failed",
        message: err instanceof Error ? err.message : "Unknown error",
        color: "red",
      });
    },
  });
}

export function useDeleteEntities() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (entity_ids: string[]) => {
      const { data, error } = await api.POST("/api/actions/delete-entity", {
        body: { entity_ids },
      });
      if (error) throw new Error(String(error));
      return data!;
    },
    onSuccess: (res) => {
      const total = res.results.length;
      const failed = res.results.filter((r) => !r.ok).length;
      const ok = total - failed;
      if (failed === 0) {
        notifications.show({
          title: "Entity Deleted",
          message: total === 1 ? "Entity deleted" : `${ok} entities deleted`,
          color: "green",
        });
        invalidateEntities(qc);
      } else if (ok === 0) {
        const firstError = res.results.find((r) => r.error)?.error;
        notifications.show({
          title: "Delete Failed",
          message:
            total === 1
              ? firstError ?? "Unknown error"
              : `${failed} entities failed to delete`,
          color: "red",
        });
      } else {
        notifications.show({
          title: "Partial Delete",
          message: `${ok} deleted, ${failed} failed`,
          color: "yellow",
        });
        invalidateEntities(qc);
      }
    },
    onError: (err) => {
      notifications.show({
        title: "Delete Failed",
        message: err instanceof Error ? err.message : "Unknown error",
        color: "red",
      });
    },
  });
}
