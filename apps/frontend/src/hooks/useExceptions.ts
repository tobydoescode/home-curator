import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/api/client";
import type { paths } from "@/api/generated";

// Pulled directly from the OpenAPI spec so a backend change surfaces at
// compile time. The endpoint's generated query type has `string | null`
// for optional string params; our ListParams uses plain optional strings,
// so the adapter just passes them through after filtering out undefineds.
type ExceptionsListQuery = NonNullable<
  paths["/api/exceptions/list"]["get"]["parameters"]["query"]
>;

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

export interface ListParams {
  search?: string;
  policy_id?: string[];
  device_id?: string[];
  area_id?: string[];
  page?: number;
  page_size?: number;
}

export function useExceptionsList(params: ListParams = {}) {
  return useQuery({
    queryKey: ["exceptions-list", params],
    queryFn: async () => {
      const query: ExceptionsListQuery = {
        search: params.search,
        policy_id: params.policy_id,
        device_id: params.device_id,
        area_id: params.area_id,
        page: params.page,
        page_size: params.page_size,
      };
      const { data, error } = await api.GET("/api/exceptions/list", { params: { query } });
      if (error) throw new Error(String(error));
      return data!;
    },
  });
}

export function useBulkDeleteExceptions() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (ids: number[]) => {
      const { data, error } = await api.POST("/api/exceptions/bulk-delete", { body: { ids } });
      if (error) throw new Error(String(error));
      return data!;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["exceptions-list"] }),
  });
}
