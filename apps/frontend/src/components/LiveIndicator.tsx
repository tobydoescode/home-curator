import { Badge, Group, Text } from "@mantine/core";
import { useEffect, useState } from "react";

import { useLiveEvents } from "@/hooks/useLiveEvents";

function formatAge(ms: number): string {
  if (ms < 2000) return "Just Now";
  if (ms < 60_000) return `${Math.round(ms / 1000)}s Ago`;
  return `${Math.round(ms / 60_000)}m Ago`;
}

export function LiveIndicator() {
  const { lastEventAt } = useLiveEvents();
  // The ticker already re-rendered every second purely to refresh this label;
  // it now carries the timestamp too, so render reads state instead of
  // calling Date.now() and producing different output for the same props.
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  return (
    <Group gap="xs">
      <Badge color="green" variant="dot">
        Live
      </Badge>
      <Text size="xs" c="dimmed">
        {lastEventAt
          ? `Updated ${formatAge(now - lastEventAt)}`
          : "Waiting For Events…"}
      </Text>
    </Group>
  );
}
