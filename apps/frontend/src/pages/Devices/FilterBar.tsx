import { Button, Checkbox, Group, Select, TextInput } from "@mantine/core";
import { IconSearch } from "@tabler/icons-react";

export interface Filters {
  q: string;
  regex: boolean;
  room: string | null;
  issue_type: string | null;
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
  room: null,
  issue_type: null,
  with_issues: false,
};

export function FilterBar({ filters, rooms, issueTypes, onChange }: Props) {
  const patch = (p: Partial<Filters>) => onChange({ ...filters, ...p });
  return (
    <Group gap="xs" wrap="wrap">
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
      <Select
        placeholder="Room: All"
        clearable
        data={rooms}
        value={filters.room}
        onChange={(v) => patch({ room: v })}
      />
      <Select
        placeholder="Issue Type: All"
        clearable
        data={issueTypes}
        value={filters.issue_type}
        onChange={(v) => patch({ issue_type: v })}
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
