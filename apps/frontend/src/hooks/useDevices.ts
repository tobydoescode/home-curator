import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";

export interface DevicesQuery {
  q?: string;
  regex?: boolean;
  room?: string;
  issue_type?: string;
  with_issues?: boolean;
  page?: number;
  page_size?: number;
}

export function useDevices(params: DevicesQuery) {
  return useQuery({
    queryKey: ["devices", params],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/devices", {
        params: { query: params },
      });
      if (error) throw new Error(String(error));
      return data!;
    },
  });
}
