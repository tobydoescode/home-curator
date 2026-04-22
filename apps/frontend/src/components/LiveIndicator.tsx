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
  const [, tick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => tick((t) => t + 1), 1000);
    return () => clearInterval(id);
  }, []);
  return (
    <Group gap="xs">
      <Badge color="green" variant="dot">
        Live
      </Badge>
      <Text size="xs" c="dimmed">
        {lastEventAt
          ? `Updated ${formatAge(Date.now() - lastEventAt)}`
          : "Waiting For Events…"}
      </Text>
    </Group>
  );
}
