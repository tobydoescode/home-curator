import { Button, Group, Stack, Table, Text, TextInput } from "@mantine/core";
import { useState } from "react";

import { useRenamePattern } from "@/hooks/useActions";

interface PreviewRow {
  device_id: string;
  matched: boolean;
  new_name?: string | null;
}

interface Props {
  deviceIds: string[];
  onClose: () => void;
}

export function RenamePatternModal({ deviceIds, onClose }: Props) {
  const [pattern, setPattern] = useState("");
  const [replacement, setReplacement] = useState("");
  const [preview, setPreview] = useState<PreviewRow[]>([]);
  const mut = useRenamePattern();

  const runPreview = async () => {
    const res = await mut.mutateAsync({
      device_ids: deviceIds,
      pattern,
      replacement,
      dry_run: true,
    });
    setPreview(res.results as PreviewRow[]);
  };
  const applyChanges = async () => {
    await mut.mutateAsync({
      device_ids: deviceIds,
      pattern,
      replacement,
      dry_run: false,
    });
    onClose();
  };

  const matchCount = preview.filter((r) => r.matched).length;

  return (
    <Stack>
      <TextInput
        label="Pattern (Regex)"
        value={pattern}
        onChange={(e) => setPattern(e.currentTarget.value)}
      />
      <TextInput
        label="Replacement"
        value={replacement}
        onChange={(e) => setReplacement(e.currentTarget.value)}
      />
      <Group>
        <Button variant="default" onClick={runPreview} disabled={!pattern || mut.isPending}>
          Preview
        </Button>
      </Group>
      {preview.length > 0 && (
        <Table withTableBorder>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Device</Table.Th>
              <Table.Th>Matched</Table.Th>
              <Table.Th>New Name</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {preview.map((r) => (
              <Table.Tr key={r.device_id}>
                <Table.Td>{r.device_id}</Table.Td>
                <Table.Td>{r.matched ? "Yes" : "No"}</Table.Td>
                <Table.Td>{r.new_name ?? "—"}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
      {matchCount > 0 && (
        <Text c="dimmed" size="xs">
          {matchCount} {matchCount === 1 ? "device" : "devices"} will be renamed.
        </Text>
      )}
      <Group justify="flex-end">
        <Button variant="subtle" onClick={onClose}>
          Cancel
        </Button>
        <Button disabled={matchCount === 0 || mut.isPending} loading={mut.isPending} onClick={applyChanges}>
          Apply Rename
        </Button>
      </Group>
    </Stack>
  );
}
