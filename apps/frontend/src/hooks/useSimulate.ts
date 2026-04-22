import { useMutation } from "@tanstack/react-query";

import { api } from "@/api/client";
import type { components } from "@/api/generated";

export function useSimulate() {
  return useMutation({
    mutationFn: async (body: components["schemas"]["SimulateRequest"]) => {
      const { data, error } = await api.POST("/api/policies/simulate", { body });
      if (error) throw new Error(String(error));
      return data!;
    },
  });
}
