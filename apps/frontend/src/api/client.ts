import createClient from "openapi-fetch";
import type { paths } from "./generated";

// In dev, Vite proxies /api to the backend. In prod (packaged addon) the
// backend serves the frontend, so /api paths resolve against the same origin.
// Tests under jsdom also resolve against `window.location.origin`.
const baseUrl =
  typeof window !== "undefined" && window.location?.origin
    ? window.location.origin
    : "";

// Dereference globalThis.fetch at call time so tests can spy on it.
const fetch: typeof globalThis.fetch = (...args) => globalThis.fetch(...args);

export const api = createClient<paths>({ baseUrl, fetch });
