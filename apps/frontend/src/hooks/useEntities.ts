import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";

export type EntitiesSortBy =
  | "entity_id"
  | "name"
  | "domain"
  | "room"
  | "device"
  | "integration"
  | "severity"
  | "created"
  | "modified";
export type EntitiesSortDir = "asc" | "desc";

export interface EntitiesQuery {
  q?: string;
  regex?: boolean;
  domain?: string[];
  room?: string[];
  integration?: string[];
  issue_type?: string[];
  with_issues?: boolean;
  show_disabled?: boolean;
  show_hidden?: boolean;
  page?: number;
  page_size?: number;
  sort_by?: EntitiesSortBy;
  sort_dir?: EntitiesSortDir;
}

export function useEntities(params: EntitiesQuery) {
  return useQuery({
    queryKey: ["entities", params],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/entities", {
        params: { query: params },
      });
      if (error) throw new Error(String(error));
      return data!;
    },
    // Mirror useDevices: keep the previous page rendered while filters
    // change so the FilterBar doesn't unmount mid-keystroke.
    placeholderData: keepPreviousData,
  });
}
