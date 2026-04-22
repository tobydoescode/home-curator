import { Button, Checkbox, Group, TextInput } from "@mantine/core";
import { IconSearch } from "@tabler/icons-react";

import { MultiPillSelect } from "@/components/MultiPillSelect";

export interface Filters {
  q: string;
  regex: boolean;
  rooms: string[];
  issue_types: string[];
  with_issues: boolean;
}

interface Props {
  filters: Filters;
  rooms: string[];
  issueTypes: string[];
  onChange: (filters: Filters) => void;
}

export const emptyFilters: Filters = {
  q: "",
  regex: false,
  rooms: [],
  issue_types: [],
  with_issues: false,
};

export function FilterBar({ filters, rooms, issueTypes, onChange }: Props) {
  const patch = (p: Partial<Filters>) => onChange({ ...filters, ...p });
  return (
    <Group gap="xs" wrap="wrap" align="flex-start">
      <TextInput
        leftSection={<IconSearch size={14} />}
        placeholder="Search By Name…"
        value={filters.q}
        onChange={(e) => patch({ q: e.currentTarget.value })}
        style={{ flex: 1, minWidth: 240 }}
      />
      <Checkbox
        label="Regex"
        checked={filters.regex}
        onChange={(e) => patch({ regex: e.currentTarget.checked })}
      />
      <MultiPillSelect
        placeholder="Room: All"
        data={rooms}
        value={filters.rooms}
        onChange={(v) => patch({ rooms: v })}
      />
      <MultiPillSelect
        placeholder="Issue Type: All"
        data={issueTypes}
        value={filters.issue_types}
        onChange={(v) => patch({ issue_types: v })}
      />
      <Checkbox
        label="With Issues Only"
        checked={filters.with_issues}
        onChange={(e) => patch({ with_issues: e.currentTarget.checked })}
      />
      <Button variant="subtle" onClick={() => onChange(emptyFilters)}>
        Clear
      </Button>
    </Group>
  );
}
