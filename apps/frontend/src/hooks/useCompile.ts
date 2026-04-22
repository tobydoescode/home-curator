import { useMutation } from "@tanstack/react-query";

import { api } from "@/api/client";
import type { components } from "@/api/generated";

type PolicyBody =
  | components["schemas"]["MissingAreaPolicy"]
  | components["schemas"]["ReappearedAfterDeletePolicy"]
  | components["schemas"]["NamingConventionPolicy"]
  | components["schemas"]["CustomPolicy"];

export function useCompile() {
  return useMutation({
    mutationFn: async (body: PolicyBody) => {
      const { data, error } = await api.POST("/api/policies/compile", { body });
      if (error) throw new Error(String(error));
      return data!;
    },
  });
}
