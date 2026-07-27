import { afterEach, describe, expect, it, vi } from "vitest";

/**
 * `baseUrl` is computed once at module load, so each case resets the module
 * registry and re-imports after arranging the document's base URI.
 */
async function requestUrlFor(baseHref: string | null): Promise<string> {
  let base: HTMLBaseElement | null = null;
  if (baseHref !== null) {
    base = document.createElement("base");
    base.href = baseHref;
    document.head.appendChild(base);
  }

  vi.resetModules();
  const fetchSpy = vi.fn(
    async (_input: Request | string, _init?: RequestInit): Promise<Response> =>
      new Response("{}", {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
  );
  vi.stubGlobal("fetch", fetchSpy);

  try {
    const { api } = await import("./client");
    await api.GET("/api/health");
    const [first] = fetchSpy.mock.calls[0];
    return typeof first === "string" ? first : first.url;
  } finally {
    base?.remove();
  }
}

describe("api client baseUrl", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it("hits the origin root when there is no base href", async () => {
    expect(await requestUrlFor(null)).toBe("http://localhost/api/health");
  });

  it("resolves under the ingress prefix when a base href is present", async () => {
    // Home Assistant serves the addon beneath /api/hassio_ingress/<token>/
    // and strips that prefix before proxying. Using window.location.origin
    // would drop it and send the request to the HA host instead.
    expect(
      await requestUrlFor("http://localhost/api/hassio_ingress/testtoken/"),
    ).toBe("http://localhost/api/hassio_ingress/testtoken/api/health");
  });
});
