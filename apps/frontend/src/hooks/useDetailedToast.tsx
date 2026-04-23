import { Anchor, Popover, Stack, Text } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useState } from "react";

export interface DetailedResult {
  id: string;
  ok: boolean;
  error?: string | null;
}

export interface DetailedToastArgs {
  /** "Entity" or "Device" — capitalised for Title Case titles. */
  kind: "Entity" | "Device";
  /** "Deleted", "Updated", "Renamed", etc. */
  action: string;
  results: DetailedResult[];
}

function ViewDetails({ failures }: { failures: DetailedResult[] }) {
  const [opened, setOpened] = useState(false);
  return (
    <Popover opened={opened} onChange={setOpened} position="top" withArrow>
      <Popover.Target>
        <Anchor
          component="button"
          type="button"
          onClick={() => setOpened((o) => !o)}
        >
          View Details
        </Anchor>
      </Popover.Target>
      <Popover.Dropdown>
        <Stack gap={4} style={{ maxHeight: 260, overflow: "auto" }}>
          {failures.map((f) => (
            <Text key={f.id} size="xs">
              <Text span fw={600}>
                {f.id}
              </Text>
              : {f.error ?? "Unknown error"}
            </Text>
          ))}
        </Stack>
      </Popover.Dropdown>
    </Popover>
  );
}

export function showDetailedResultToast({
  kind,
  action,
  results,
}: DetailedToastArgs): void {
  const total = results.length;
  const failures = results.filter((r) => !r.ok);
  const ok = total - failures.length;
  const kindPlural = kind === "Entity" ? "Entities" : "Devices";

  if (failures.length === 0) {
    notifications.show({
      title: `${kind} ${action}`,
      message:
        total === 1
          ? `${kind} ${action.toLowerCase()}`
          : `${ok} ${kindPlural} ${action}`,
      color: "green",
    });
    return;
  }

  if (ok === 0) {
    const first = failures[0]?.error ?? "Unknown error";
    notifications.show({
      title: `${action} Failed`,
      message:
        total === 1
          ? first
          : `${failures.length} ${kindPlural.toLowerCase()} failed to ${action.toLowerCase()}`,
      color: "red",
      autoClose: 8000,
    });
    if (failures.length > 1) {
      notifications.show({
        title: `${action} Failures`,
        message: <ViewDetails failures={failures} />,
        color: "red",
        autoClose: 8000,
      });
    }
    return;
  }

  notifications.show({
    title: `Partial ${action}`,
    message: (
      <span>
        {ok} {action.toLowerCase()}, {failures.length} failed.{" "}
        <ViewDetails failures={failures} />
      </span>
    ),
    color: "yellow",
    autoClose: 8000,
  });
}
