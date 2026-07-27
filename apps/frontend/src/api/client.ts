import createClient from "openapi-fetch";
import type { paths } from "./generated";

// Resolved from `document.baseURI` rather than `window.location.origin` so
// the app works under Home Assistant ingress, where it is served beneath a
// per-session path prefix (`/api/hassio_ingress/<token>/`). The backend
// injects that prefix as `<base href>`, which is what baseURI reflects.
//
// `window.location.origin` would drop the prefix and send every request to
// the Home Assistant host instead of the add-on. Reading the current URL
// directly would be wrong too, since it varies with the active route.
//
// Outside ingress there is no prefix: in dev this is `http://localhost:5173`
// (Vite proxies /api), in the packaged addon it is the origin the backend
// serves from, and under jsdom it is the test origin.
const baseUrl =
  typeof document !== "undefined" && document.baseURI
    ? document.baseURI.replace(/\/$/, "")
    : "";

// Dereference globalThis.fetch at call time so tests can spy on it.
const fetch: typeof globalThis.fetch = (...args) => globalThis.fetch(...args);

export const api = createClient<paths>({ baseUrl, fetch });
