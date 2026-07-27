"""Serve the built frontend in a way that survives Home Assistant ingress.

Home Assistant serves an ingress add-on under a per-session path prefix
(`/api/hassio_ingress/<token>/`) and strips that prefix before proxying to
us. The browser therefore sees URLs the add-on never does, so anything the
page emits as an absolute path — `/assets/index.js`, `/api/devices`,
`/api/events` — resolves against the Home Assistant host instead of the
add-on and 404s.

Relative paths alone do not fix it. At `…/<token>/settings/devices` a
relative `./assets/index.js` resolves to `…/<token>/settings/assets/index.js`,
so a hard refresh on any nested route breaks.

The prefix has to come from somewhere absolute, and Home Assistant supplies
exactly that: it sets an `X-Ingress-Path` header on every proxied request.
We inject it as `<base href>`, which every relative URL on the page then
resolves against regardless of route depth. The frontend is built with Vite's
`base: "./"` so its asset URLs are relative for that tag to act on.

Outside ingress the header is absent and the injected tag is `<base href="/">`,
which is what a plain SPA at the origin root wants anyway.
"""

import html
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

INGRESS_PATH_HEADER = "X-Ingress-Path"

_BASE_TAG = re.compile(r"<base[^>]*>", re.IGNORECASE)
_HEAD_OPEN = re.compile(r"<head(\s[^>]*)?>", re.IGNORECASE)


def with_base_href(index_html: str, ingress_path: str) -> str:
    """Return `index_html` with a `<base href>` for the given ingress prefix.

    `ingress_path` is the raw header value (no trailing slash, e.g.
    `/api/hassio_ingress/abc123`) or an empty string when not behind ingress.
    It is escaped before interpolation — it arrives from a request header.
    """
    href = html.escape(f"{ingress_path.rstrip('/')}/", quote=True)
    tag = f'<base href="{href}">'
    # Drop any existing tag so repeated injection cannot stack.
    stripped = _BASE_TAG.sub("", index_html)
    injected, count = _HEAD_OPEN.subn(lambda m: m.group(0) + tag, stripped, count=1)
    return injected if count else tag + stripped


def mount_spa(app: FastAPI, static_root: Path) -> None:
    """Serve the built frontend from `static_root`.

    Registered after the API routers so `/api/*` always wins. Hashed assets
    are served straight off disk; everything else falls through to
    `index.html` so client-side routes survive a refresh.
    """
    resolved_root = static_root.resolve()
    assets = resolved_root / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    index_path = resolved_root / "index.html"

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str, request: Request) -> Response:
        # An unmatched /api/* path is a genuine 404, not a client-side route.
        # Without this the SPA fallback would answer API typos with HTML.
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")

        candidate = (resolved_root / full_path).resolve()
        if (
            full_path
            and candidate.is_file()
            # `full_path` is attacker-controlled, so confirm the resolved path
            # did not escape the static root via `..` segments.
            and candidate.is_relative_to(resolved_root)
        ):
            return FileResponse(candidate)

        # Read per request rather than caching: the file is served once per
        # page load, and a stale cache would be a confusing failure mode.
        return HTMLResponse(
            with_base_href(
                index_path.read_text(encoding="utf-8"),
                request.headers.get(INGRESS_PATH_HEADER, ""),
            )
        )
