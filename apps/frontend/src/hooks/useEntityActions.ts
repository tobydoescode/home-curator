import { notifications } from "@mantine/notifications";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "@/api/client";

import { showDetailedResultToast, type DetailedResult } from "./useDetailedToast";

function invalidateEntities(qc: ReturnType<typeof useQueryClient>): void {
  qc.invalidateQueries({ queryKey: ["entities"] });
}

function toDetailed<
  T extends { entity_id: string; ok: boolean; error?: string | null },
>(rows: T[]): DetailedResult[] {
  return rows.map((r) => ({
    id: r.entity_id,
    ok: r.ok,
    error: r.error ?? undefined,
  }));
}

// ---- single-entity PATCH ------------------------------------------------
export interface UpdateEntityChanges {
  new_entity_id?: string;
  name?: string | null;
  area_id?: string | null;
  disabled_by?: string | null;
  hidden_by?: string | null;
  icon?: string | null;
}

export function useUpdateEntity() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      entity_id,
      changes,
    }: {
      entity_id: string;
      changes: UpdateEntityChanges;
    }) => {
      const { data, error } = await api.PATCH("/api/entities/{entity_id}", {
        params: { path: { entity_id } },
        body: changes,
      });
      if (error) throw new Error(String(error));
      return data!;
    },
    onSuccess: (_res, vars) => {
      const renamed = Boolean(vars.changes.new_entity_id);
      notifications.show({
        title: renamed ? "Entity Renamed" : "Entity Updated",
        message: "Changes saved",
        color: "green",
      });
      invalidateEntities(qc);
    },
    onError: (err) => {
      notifications.show({
        title: "Save Failed",
        message: err instanceof Error ? err.message : "Unknown error",
        color: "red",
      });
    },
  });
}

// ---- bulk delete --------------------------------------------------------
export function useDeleteEntities() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (entity_ids: string[]) => {
      const { data, error } = await api.POST("/api/entities/bulk-delete", {
        body: { entity_ids },
      });
      if (error) throw new Error(String(error));
      return data!;
    },
    onSuccess: (res) => {
      showDetailedResultToast({
        kind: "Entity",
        action: "Deleted",
        results: toDetailed(res.results),
      });
      const anyOk = res.results.some((r) => r.ok);
      if (anyOk) invalidateEntities(qc);
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

// ---- bulk assign room ---------------------------------------------------
export function useAssignRoomEntities() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: {
      entity_ids: string[];
      area_id: string | null;
    }) => {
      const { data, error } = await api.POST(
        "/api/entities/assign-room",
        { body },
      );
      if (error) throw new Error(String(error));
      return data!;
    },
    onSuccess: (res) => {
      showDetailedResultToast({
        kind: "Entity",
        action: "Updated",
        results: toDetailed(res.results),
      });
      invalidateEntities(qc);
    },
  });
}

// ---- bulk dual-regex rename --------------------------------------------
export interface RenameEntityPatternBody {
  entity_ids: string[];
  id_pattern?: string;
  id_replacement?: string;
  name_pattern?: string;
  name_replacement?: string;
  dry_run: boolean;
}

export function useRenameEntityPattern() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: RenameEntityPatternBody) => {
      const { data, error } = await api.POST(
        "/api/entities/rename-pattern",
        { body },
      );
      if (error) throw new Error(String(error));
      return data!;
    },
    onSuccess: (res, vars) => {
      if (vars.dry_run) return;
      if (res.error) {
        notifications.show({
          title: "Rename Failed",
          message: res.error,
          color: "red",
        });
        return;
      }
      showDetailedResultToast({
        kind: "Entity",
        action: "Renamed",
        results: toDetailed(res.results),
      });
      invalidateEntities(qc);
    },
  });
}

// ---- bulk enable/disable/show/hide -------------------------------------
export function useEntityState() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: {
      entity_ids: string[];
      field: "disabled_by" | "hidden_by";
      value: "user" | null;
    }) => {
      const { data, error } = await api.POST("/api/entities/state", {
        body,
      });
      if (error) throw new Error(String(error));
      return data!;
    },
    onSuccess: (res, vars) => {
      const actionWord =
        vars.field === "disabled_by"
          ? vars.value === null
            ? "Enabled"
            : "Disabled"
          : vars.value === null
            ? "Shown"
            : "Hidden";
      showDetailedResultToast({
        kind: "Entity",
        action: actionWord,
        results: toDetailed(res.results),
      });
      invalidateEntities(qc);
    },
  });
}
