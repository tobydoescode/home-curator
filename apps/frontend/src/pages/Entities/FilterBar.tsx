import { Button, Checkbox, Group, TextInput } from "@mantine/core";
import { IconSearch } from "@tabler/icons-react";

import { MultiPillSelect } from "@/components/MultiPillSelect";

export interface Filters {
  q: string;
  regex: boolean;
  domains: string[];
  rooms: string[];
  integrations: string[];
  issue_types: string[];
  with_issues: boolean;
  show_disabled: boolean;
  show_hidden: boolean;
}

export const emptyFilters: Filters = {
  q: "",
  regex: false,
  domains: [],
  rooms: [],
  integrations: [],
  issue_types: [],
  with_issues: false,
  show_disabled: false,
  show_hidden: false,
};

// Sentinel value used to represent "No Room" picks in the room multi-select.
// The backend recognises the same sentinel via the `__none__` query value.
export const NO_ROOM_SENTINEL = "__none__";
export const NO_ROOM_LABEL = "No Room";

interface Props {
  filters: Filters;
  domains: string[];
  rooms: string[];           // human-readable area names (no sentinel)
  integrations: string[];
  issueTypes: string[];
  domainCounts?: Record<string, number>;
  roomCounts?: Record<string, number>;
  integrationCounts?: Record<string, number>;
  issueTypeCounts?: Record<string, number>;
  onChange: (filters: Filters) => void;
  /** Right-hand slot — typically the column-visibility gear. */
  rightSlot?: React.ReactNode;
}

export function FilterBar({
  filters,
  domains,
  rooms,
  integrations,
  issueTypes,
  domainCounts,
  roomCounts,
  integrationCounts,
  issueTypeCounts,
  onChange,
  rightSlot,
}: Props) {
  const patch = (p: Partial<Filters>) => onChange({ ...filters, ...p });

  // Inject a "No Room" pseudo-option at the top of the room list. Selecting
  // it stores `__none__` in the filter; the backend interprets that as
  // "rooms with no area assignment".
  const roomOptions = [NO_ROOM_LABEL, ...rooms];
  const roomCountsWithSentinel = {
    ...(roomCounts ?? {}),
    [NO_ROOM_LABEL]: roomCounts?.[NO_ROOM_SENTINEL] ?? 0,
  };
  const labelToValue = (label: string): string =>
    label === NO_ROOM_LABEL ? NO_ROOM_SENTINEL : label;
  const valueToLabel = (value: string): string =>
    value === NO_ROOM_SENTINEL ? NO_ROOM_LABEL : value;

  return (
    <Group gap="xs" wrap="wrap" align="center">
      <TextInput
        leftSection={<IconSearch size={14} />}
        placeholder="Search Entity ID Or Name…"
        value={filters.q}
        onChange={(e) => patch({ q: e.currentTarget.value })}
        style={{ flex: 1, minWidth: 240 }}
        h={32}
      />
      <Checkbox
        label="Regex"
        checked={filters.regex}
        onChange={(e) => patch({ regex: e.currentTarget.checked })}
      />
      <MultiPillSelect
        placeholder="Domain: All"
        data={domains}
        value={filters.domains}
        counts={domainCounts}
        onChange={(v) => patch({ domains: v })}
      />
      <MultiPillSelect
        placeholder="Room: All"
        data={roomOptions}
        value={filters.rooms.map(valueToLabel)}
        counts={roomCountsWithSentinel}
        onChange={(v) => patch({ rooms: v.map(labelToValue) })}
      />
      <MultiPillSelect
        placeholder="Integration: All"
        data={integrations}
        value={filters.integrations}
        counts={integrationCounts}
        onChange={(v) => patch({ integrations: v })}
      />
      <MultiPillSelect
        placeholder="Issue Type: All"
        data={issueTypes}
        value={filters.issue_types}
        counts={issueTypeCounts}
        onChange={(v) => patch({ issue_types: v })}
      />
      <Checkbox
        label="With Issues Only"
        checked={filters.with_issues}
        onChange={(e) => patch({ with_issues: e.currentTarget.checked })}
      />
      <Checkbox
        label="Show Disabled"
        checked={filters.show_disabled}
        onChange={(e) => patch({ show_disabled: e.currentTarget.checked })}
      />
      <Checkbox
        label="Show Hidden"
        checked={filters.show_hidden}
        onChange={(e) => patch({ show_hidden: e.currentTarget.checked })}
      />
      <Button variant="subtle" onClick={() => onChange(emptyFilters)}>
        Clear
      </Button>
      {rightSlot}
    </Group>
  );
}
