/**
 * Where the app is served from.
 *
 * Home Assistant ingress serves the addon beneath a per-session path prefix
 * (`/api/hassio_ingress/<token>/`) and strips it before proxying, so the
 * backend injects that prefix into `index.html` as `<base href>`. Everything
 * the app emits — API calls, the SSE stream, router paths — has to resolve
 * against it.
 *
 * The `<base>` element is read directly rather than via `document.baseURI`.
 * `baseURI` falls back to the *document's own URL* when no `<base>` element
 * exists, which is the case on the Vite dev server and anywhere else the
 * backend is not serving the page. Deriving from it meant that on `/devices`
 * the API base became `http://host/devices`, so `GET /api/devices` went to
 * `/devices/api/devices`, the dev server answered with `index.html`, and
 * every query died on `JSON.parse` of `<!doctype`. The router basename went
 * wrong the same way, turning `/devices` into `/devices/devices`.
 */

function baseElementHref(): string | null {
  if (typeof document === "undefined") return null;
  const el = document.querySelector("base");
  // `el.href` is resolved to an absolute URL by the DOM; an empty attribute
  // yields an empty string, which we treat as absent.
  return el?.href ? el.href : null;
}

/**
 * Absolute URL prefix for API requests, without a trailing slash.
 *
 * With an injected `<base href>` this is the ingress prefix. Without one it
 * is the origin — never the current page's URL, which changes per route.
 */
export function appBaseUrl(): string {
  const href = baseElementHref();
  if (href) return href.replace(/\/$/, "");
  if (typeof window !== "undefined" && window.location?.origin) {
    return window.location.origin;
  }
  return "";
}

/**
 * Path for React Router's `basename`.
 *
 * `"/"` outside ingress, so routes are matched from the origin root.
 */
export function appBasename(): string {
  const href = baseElementHref();
  if (!href) return "/";
  return new URL(href).pathname;
}
