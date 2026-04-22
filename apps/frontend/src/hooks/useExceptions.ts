import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/api/client";

export function useAcknowledgeException() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: {
      device_id: string;
      policy_id: string;
      note?: string;
      acknowledged_by?: string;
    }) => {
      const { error } = await api.POST("/api/exceptions", { body });
      if (error) throw new Error(String(error));
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["devices"] }),
  });
}

export function useClearException() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      device_id,
      policy_id,
    }: {
      device_id: string;
      policy_id: string;
    }) => {
      const { error } = await api.DELETE("/api/exceptions/{device_id}/{policy_id}", {
        params: { path: { device_id, policy_id } },
      });
      if (error) throw new Error(String(error));
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["devices"] }),
  });
}

export function useExceptionsForDevice(deviceId: string | null) {
  return useQuery({
    queryKey: ["exceptions", deviceId],
    enabled: deviceId !== null,
    queryFn: async () => {
      const { data, error } = await api.GET("/api/exceptions", {
        params: { query: { device_id: deviceId! } },
      });
      if (error) throw new Error(String(error));
      return data!;
    },
  });
}
