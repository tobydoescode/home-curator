import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/api/client";
import type { components } from "@/api/generated";

export type PoliciesFileShape = components["schemas"]["PoliciesFile"];

export function usePolicies() {
  return useQuery({
    queryKey: ["policies"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/policies");
      if (error) throw new Error(String(error));
      return data!;
    },
  });
}

export function useUpdatePolicies() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: PoliciesFileShape) => {
      const { data, error } = await api.PUT("/api/policies", { body });
      if (error) throw new Error(String(error));
      return data!;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["policies"] });
      qc.invalidateQueries({ queryKey: ["devices"] });
    },
  });
}
