import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { subscribeSSE, type SSEEvent } from "@/api/sse";

export function useLiveEvents() {
  const qc = useQueryClient();
  const [lastEventAt, setLastEventAt] = useState<number | null>(null);
  useEffect(() => {
    // EventSource isn't available in test environments.
    if (typeof EventSource === "undefined") return;
    const unsub = subscribeSSE((e: SSEEvent) => {
      setLastEventAt(Date.now());
      if (e.kind === "devices_changed")
        qc.invalidateQueries({ queryKey: ["devices"] });
      if (e.kind === "policies_changed")
        qc.invalidateQueries({ queryKey: ["policies"] });
      if (
        e.kind === "entities_changed" ||
        e.kind === "entity_updated" ||
        e.kind === "entity_deleted"
      )
        qc.invalidateQueries({ queryKey: ["entities"] });
    });
    return unsub;
  }, [qc]);
  return { lastEventAt };
}
