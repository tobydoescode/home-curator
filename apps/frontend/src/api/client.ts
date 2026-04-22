import createClient from "openapi-fetch";
import type { paths } from "./generated";

// In dev, Vite proxies /api to the backend. In prod (packaged addon) the
// backend serves the frontend, so relative /api paths work unchanged.
export const api = createClient<paths>({ baseUrl: "" });
