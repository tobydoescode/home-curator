import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";

export type DevicesSortBy =
  | "name"
  | "room"
  | "severity"
  | "integration"
  | "created"
  | "modified";
export type DevicesSortDir = "asc" | "desc";

export interface DevicesQuery {
  q?: string;
  regex?: boolean;
  room?: string[];
  issue_type?: string[];
  with_issues?: boolean;
  page?: number;
  page_size?: number;
  sort_by?: DevicesSortBy;
  sort_dir?: DevicesSortDir;
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
    // Keep the previous page rendered while refetching on filter/search
    // changes — otherwise the FilterBar unmounts on every keystroke,
    // stealing focus and flashing the UI.
    placeholderData: keepPreviousData,
  });
}
