import { notifications } from "@mantine/notifications";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "@/api/client";

export function useResync() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/api/cache/resync", {});
      if (error) {
        const detail =
          typeof error === "object" && error !== null && "detail" in error
            ? String((error as { detail: unknown }).detail)
            : typeof error === "string"
              ? error
              : JSON.stringify(error);
        throw new Error(detail);
      }
      return data!;
    },
    onSuccess: (diff) => {
      const changed =
        diff.added
        + diff.removed
        + diff.updated
        + (diff.entity_added ?? 0)
        + (diff.entity_removed ?? 0)
        + (diff.entity_updated ?? 0);
      const message =
        changed === 0
          ? "Resynced"
          : `Resynced — ${changed} ${changed === 1 ? "change" : "changes"} detected`;
      notifications.show({
        title: "Resync",
        message,
        color: "green",
      });
      qc.invalidateQueries({ queryKey: ["devices"] });
      qc.invalidateQueries({ queryKey: ["entities"] });
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
