import { appBaseUrl } from "./basePath";

export type SSEEvent =
  | { kind: "devices_changed" }
  | { kind: "policies_changed" }
  | { kind: "entities_changed" }
  | { kind: "entity_updated"; entity_id: string }
  | { kind: "entity_deleted"; entity_id: string }
  | { kind: "exceptions_changed" };

export function subscribeSSE(
  onEvent: (e: SSEEvent) => void,
  onError?: (err: unknown) => void,
): () => void {
  // Resolved against the app's base so the stream reaches the addon under
  // ingress. An absolute "/api/events" would reach the Home Assistant host
  // instead.
  const src = new EventSource(`${appBaseUrl()}/api/events`);
  src.addEventListener("message", (e) => {
    try {
      onEvent(JSON.parse(e.data) as SSEEvent);
    } catch (err) {
      onError?.(err);
    }
  });
  src.addEventListener("error", (e) => onError?.(e));
  return () => src.close();
}
