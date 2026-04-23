import { notifications } from "@mantine/notifications";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "@/api/client";

export function useResync() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/api/devices/resync", {});
      if (error) throw new Error(String(error));
      return data!;
    },
    onSuccess: (diff) => {
      const changed = diff.added + diff.removed + diff.updated;
      const message =
        changed === 0
          ? "Resynced"
          : `Resynced — ${changed} ${changed === 1 ? "device" : "devices"} changed`;
      notifications.show({
        title: "Resync",
        message,
        color: "green",
      });
      qc.invalidateQueries({ queryKey: ["devices"] });
      qc.invalidateQueries({ queryKey: ["policies"] });
    },
    onError: (err) => {
      notifications.show({
        title: "Resync Failed",
        message: err instanceof Error ? err.message : "Unknown error",
        color: "red",
      });
    },
  });
}
