import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { appBaseUrl, appBasename } from "./basePath";

function setBaseHref(href: string): void {
  const el = document.createElement("base");
  el.href = href;
  document.head.appendChild(el);
}

describe("appBaseUrl", () => {
  beforeEach(() => {
    window.history.pushState({}, "", "/");
  });

  afterEach(() => {
    document.querySelectorAll("base").forEach((el) => el.remove());
    window.history.pushState({}, "", "/");
  });

  it("uses the origin when no base href is present", () => {
    expect(appBaseUrl()).toBe("http://localhost");
  });

  it("uses the origin on a nested route when no base href is present", () => {
    // The regression this file exists for. `document.baseURI` falls back to
    // the document's own URL when there is no <base> element, so deriving
    // from it sent GET /api/devices to /devices/api/devices — which the dev
    // server answered with index.html, and JSON.parse died on "<!doctype".
    window.history.pushState({}, "", "/settings/devices");
    expect(appBaseUrl()).toBe("http://localhost");
  });

  it("uses the injected base href under ingress", () => {
    setBaseHref("http://localhost/api/hassio_ingress/testtoken/");
    expect(appBaseUrl()).toBe("http://localhost/api/hassio_ingress/testtoken");
  });

  it("uses the injected base href regardless of the current route", () => {
    setBaseHref("http://localhost/api/hassio_ingress/testtoken/");
    window.history.pushState(
      {},
      "",
      "/api/hassio_ingress/testtoken/settings/devices",
    );
    expect(appBaseUrl()).toBe("http://localhost/api/hassio_ingress/testtoken");
  });
});

describe("appBasename", () => {
  beforeEach(() => {
    window.history.pushState({}, "", "/");
  });

  afterEach(() => {
    document.querySelectorAll("base").forEach((el) => el.remove());
    window.history.pushState({}, "", "/");
  });

  it("is the router root when no base href is present", () => {
    expect(appBasename()).toBe("/");
  });

  it("stays the router root on a nested route", () => {
    // Otherwise the router treats the current path as its own base and
    // doubles it — /devices became /devices/devices.
    window.history.pushState({}, "", "/devices");
    expect(appBasename()).toBe("/");
  });

  it("is the ingress prefix when a base href is present", () => {
    setBaseHref("http://localhost/api/hassio_ingress/testtoken/");
    expect(appBasename()).toBe("/api/hassio_ingress/testtoken/");
  });
});
