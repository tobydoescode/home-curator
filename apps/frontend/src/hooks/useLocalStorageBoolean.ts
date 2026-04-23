import { useCallback, useState } from "react";

export function useLocalStorageBoolean(
  key: string,
  defaultValue: boolean,
): [boolean, () => void] {
  const [value, setValue] = useState<boolean>(() => {
    if (typeof window === "undefined") return defaultValue;
    const raw = window.localStorage.getItem(key);
    if (raw === "true") return true;
    if (raw === "false") return false;
    return defaultValue;
  });

  const toggle = useCallback(() => {
    setValue((prev) => {
      const next = !prev;
      if (typeof window !== "undefined") {
        window.localStorage.setItem(key, String(next));
      }
      return next;
    });
  }, [key]);

  return [value, toggle];
}
