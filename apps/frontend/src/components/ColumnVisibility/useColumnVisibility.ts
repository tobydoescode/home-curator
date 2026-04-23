import { useCallback, useMemo, useState } from "react";

export interface UseColumnVisibilityArgs {
  /** Stable localStorage key. Use `home-curator:columns:<scope>`. */
  storageKey: string;
  /** Every column id the table renders. */
  allColumns: readonly string[];
  /** The subset that should be visible on first load (no localStorage entry). */
  defaultVisible: readonly string[];
}

export interface UseColumnVisibilityReturn {
  /** TanStack Table `state.columnVisibility` shape: { [id]: boolean }. */
  visible: Record<string, boolean>;
  /** Flip a single column. */
  toggle: (id: string) => void;
  /** Restore defaults and clear localStorage. */
  reset: () => void;
  /** Convenience predicate. */
  isVisible: (id: string) => boolean;
}

function readPersisted(key: string): string[] | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(key);
  if (raw === null) return null;
  try {
    const parsed: unknown = JSON.parse(raw);
    if (Array.isArray(parsed) && parsed.every((x) => typeof x === "string")) {
      return parsed as string[];
    }
  } catch {
    // Fall through; treat as missing.
  }
  return null;
}

function writePersisted(key: string, ids: string[]): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(key, JSON.stringify(ids));
}

function clearPersisted(key: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(key);
}

// Persisted shape is the visible-id list (not the full {id: bool} map) so
// adding a brand-new column later doesn't leak into existing users' saved
// state — it picks up its `defaultVisible` value automatically.
export function useColumnVisibility({
  storageKey,
  allColumns,
  defaultVisible,
}: UseColumnVisibilityArgs): UseColumnVisibilityReturn {
  const [visibleIds, setVisibleIds] = useState<string[]>(() => {
    const stored = readPersisted(storageKey);
    return stored ?? Array.from(defaultVisible);
  });

  const visible = useMemo<Record<string, boolean>>(() => {
    const out: Record<string, boolean> = {};
    for (const id of allColumns) out[id] = visibleIds.includes(id);
    return out;
  }, [allColumns, visibleIds]);

  const toggle = useCallback(
    (id: string) => {
      setVisibleIds((prev) => {
        const next = prev.includes(id)
          ? prev.filter((x) => x !== id)
          : [...prev, id];
        writePersisted(storageKey, next);
        return next;
      });
    },
    [storageKey],
  );

  const reset = useCallback(() => {
    clearPersisted(storageKey);
    setVisibleIds(Array.from(defaultVisible));
  }, [storageKey, defaultVisible]);

  const isVisible = useCallback(
    (id: string) => visibleIds.includes(id),
    [visibleIds],
  );

  return { visible, toggle, reset, isVisible };
}
