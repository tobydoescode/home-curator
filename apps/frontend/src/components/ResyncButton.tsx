import { ActionIcon, Tooltip } from "@mantine/core";
import { IconRefresh } from "@tabler/icons-react";

import { useResync } from "@/hooks/useResync";

export function ResyncButton() {
  const resync = useResync();
  return (
    <Tooltip label="Resync With Home Assistant" withArrow>
      <ActionIcon
        variant="subtle"
        aria-label="Resync with Home Assistant"
        onClick={() => resync.mutate()}
        loading={resync.isPending}
      >
        <IconRefresh size={18} />
      </ActionIcon>
    </Tooltip>
  );
}
