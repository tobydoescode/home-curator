import createClient from "openapi-fetch";
import { appBaseUrl } from "./basePath";
import type { paths } from "./generated";

// See basePath.ts: this is the injected <base href> under Home Assistant
// ingress, and the plain origin everywhere else. Deliberately not
// document.baseURI, which silently falls back to the current page URL when
// no <base> element is present.
const baseUrl = appBaseUrl();

// Dereference globalThis.fetch at call time so tests can spy on it.
const fetch: typeof globalThis.fetch = (...args) => globalThis.fetch(...args);

export const api = createClient<paths>({ baseUrl, fetch });
