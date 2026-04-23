import { useMutation, useQueryClient } from "@tanstack/react-query";
import { notifications } from "@mantine/notifications";

import { api } from "@/api/client";

function invalidateDevices(queryClient: ReturnType<typeof useQueryClient>) {
  queryClient.invalidateQueries({ queryKey: ["devices"] });
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
      const fails = res.results.filter((r) => !r.ok);
      notifications.show({
        title: "Assign Room",
        message: fails.length
          ? `${res.results.length - fails.length} Updated, ${fails.length} Failed`
          : `${res.results.length} Updated`,
        color: fails.length ? "yellow" : "green",
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
    onSuccess: (_res, vars) => {
      if (!vars.dry_run) invalidateDevices(qc);
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
    onSuccess: () => invalidateDevices(qc),
  });
}
