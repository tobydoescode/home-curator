import { useMutation, useQueryClient } from "@tanstack/react-query";
import { notifications } from "@mantine/notifications";

import { api } from "@/api/client";

import { showDetailedResultToast, type DetailedResult } from "./useDetailedToast";

function invalidateDevices(queryClient: ReturnType<typeof useQueryClient>) {
  queryClient.invalidateQueries({ queryKey: ["devices"] });
}

function toDetailedDevice<
  T extends { device_id: string; ok: boolean; error?: string | null },
>(rows: T[]): DetailedResult[] {
  return rows.map((r) => ({
    id: r.device_id,
    ok: r.ok,
    error: r.error ?? undefined,
  }));
}

export function useAssignRoom() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { device_ids: string[]; area_id: string }) => {
      const { data, error } = await api.POST("/api/actions/assign-room", { body });
      if (error) throw new Error(String(error));
      return data!;
    },
    onSuccess: (res) => {
      showDetailedResultToast({
        kind: "Device",
        action: "Updated",
        results: toDetailedDevice(res.results),
      });
      invalidateDevices(qc);
    },
  });
}

export function useRename() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { device_id: string; name_by_user: string }) => {
      const { error } = await api.POST("/api/actions/rename", { body });
      if (error) throw new Error(String(error));
    },
    onSuccess: () => invalidateDevices(qc),
  });
}

export function useRenamePattern() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: {
      device_ids: string[];
      pattern: string;
      replacement: string;
      dry_run: boolean;
    }) => {
      const { data, error } = await api.POST("/api/actions/rename-pattern", { body });
      if (error) throw new Error(String(error));
      return data!;
    },
    onSuccess: (res, vars) => {
      if (vars.dry_run) return;
      showDetailedResultToast({
        kind: "Device",
        action: "Renamed",
        results: toDetailedDevice(res.results ?? []),
      });
      invalidateDevices(qc);
    },
  });
}

export function useUpdateDevice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      device_id,
      changes,
    }: {
      device_id: string;
      changes: { name_by_user?: string | null; area_id?: string | null };
    }) => {
      const { error } = await api.PATCH("/api/actions/device/{device_id}", {
        params: { path: { device_id } },
        body: changes,
      });
      if (error) throw new Error(String(error));
    },
    onSuccess: () => {
      notifications.show({
        title: "Device Updated",
        message: "Changes saved",
        color: "green",
      });
      invalidateDevices(qc);
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

export function useDeleteDevices() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (device_ids: string[]) => {
      const { data, error } = await api.POST("/api/actions/delete", {
        body: { device_ids },
      });
      if (error) throw new Error(String(error));
      return data!;
    },
    onSuccess: (res) => {
      showDetailedResultToast({
        kind: "Device",
        action: "Deleted",
        results: toDetailedDevice(res.results),
      });
      // Only invalidate when at least one delete actually succeeded.
      if (res.results.some((r) => r.ok)) invalidateDevices(qc);
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
