import "@testing-library/jest-dom/vitest";

import { MantineProvider } from "@mantine/core";
import { ModalsProvider } from "@mantine/modals";
import { Notifications } from "@mantine/notifications";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { EntitySettingsPage } from "./EntitySettingsPage";

const POLICIES_FILE = {
  version: 1,
  policies: [
    {
      id: "entity-naming",
      type: "entity_naming_convention",
      enabled: true,
      severity: "warning",
      name: {
        global: { preset: "title-case" },
        starts_with_room: false,
        rooms: [],
      },
      entity_id: { starts_with_room: false, rooms: [] },
    },
    {
      id: "entity-missing-area",
      type: "entity_missing_area",
      enabled: true,
      severity: "info",
      require_own_area: false,
    },
    {
      id: "entity-reappeared",
      type: "reappeared_after_delete",
      scope: "entities",
      enabled: false,
      severity: "info",
    },
    {
      id: "aqara-needs-name",
      type: "custom",
      scope: "entities",
      enabled: true,
      severity: "info",
      when: 'entity.platform == "aqara_ble"',
      assert: "entity.name != null",
      message: "Aqara entity without a friendly name",
    },
  ],
};

beforeEach(() => {
  window.HTMLElement.prototype.scrollIntoView = vi.fn();
  vi.stubGlobal(
    "fetch",
    vi.fn(async (req: Request | string) => {
      const url = typeof req === "string" ? req : req.url;
      const method = typeof req === "string" ? "GET" : req.method;
      if (url.includes("/api/policies/file") && method === "GET") {
        return new Response(JSON.stringify(POLICIES_FILE), { status: 200 });
      }
      if (url.includes("/api/policies") && method === "PUT") {
        return new Response(JSON.stringify({ ok: true }), { status: 200 });
      }
      if (url.includes("/api/areas")) {
        return new Response(
          JSON.stringify([{ id: "garage", name: "Garage" }]),
          { status: 200 },
        );
      }
      return new Response("{}", { status: 200 });
    }),
  );
});

afterEach(() => vi.restoreAllMocks());

function wrap() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <MantineProvider>
      <Notifications />
      <ModalsProvider>
        <QueryClientProvider client={qc}>
          <MemoryRouter>
            <EntitySettingsPage />
          </MemoryRouter>
        </QueryClientProvider>
      </ModalsProvider>
    </MantineProvider>,
  );
}

describe("EntitySettingsPage", () => {
  it("renders Naming / Built-In / Custom sections once policies load", async () => {
    wrap();
    expect(
      await screen.findByRole("heading", { name: /Entity Settings/i }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: /Friendly Name/i }),
    ).toBeInTheDocument();
    expect(
      await screen.findAllByRole("heading", { name: /Entity ID/i }),
    ).toBeTruthy();
    expect(
      await screen.findByRole("heading", { name: /Built-In Rules/i }),
    ).toBeInTheDocument();
  });

  it("Friendly Name block renders a Preset dropdown; Entity ID block has a Derived Pattern", async () => {
    wrap();
    await screen.findByRole("heading", { name: /Friendly Name/i });
    const presets = await screen.findAllByLabelText(/preset/i);
    expect(presets.length).toBeGreaterThan(0);
    expect(
      await screen.findByLabelText(/Derived Pattern/i),
    ).toBeInTheDocument();
  });

  it("Require Own Area toggle emits policy-level require_own_area change", async () => {
    const user = userEvent.setup();
    wrap();
    await screen.findByRole("heading", { name: /Entity Missing Area/i });
    await user.click(screen.getByRole("switch", { name: /require own area/i }));
    await user.click(screen.getByRole("button", { name: /Save/i }));
    await waitFor(() => {
      const puts = (globalThis.fetch as any).mock.calls.filter((c: any[]) => {
        const r = c[0] as Request;
        return r.method === "PUT" && r.url.includes("/api/policies");
      });
      expect(puts.length).toBe(1);
    });
    const put = (globalThis.fetch as any).mock.calls.find(
      (c: any[]) => (c[0] as Request).method === "PUT",
    )[0] as Request;
    const body = await put.json();
    const missing = body.policies.find(
      (p: any) => p.type === "entity_missing_area",
    );
    expect(missing.require_own_area).toBe(true);
  });

  it("Custom Rules section shows only entity-scoped custom rules", async () => {
    wrap();
    expect(await screen.findByText("aqara-needs-name")).toBeInTheDocument();
  });

  it("Save posts the full draft", async () => {
    const user = userEvent.setup();
    wrap();
    await screen.findByRole("heading", { name: /Entity Settings/i });
    await user.click(screen.getByRole("button", { name: /Save/i }));
    await waitFor(() => {
      const put = (globalThis.fetch as any).mock.calls.find(
        (c: any[]) => (c[0] as Request).method === "PUT",
      );
      expect(put).toBeDefined();
    });
  });

  it("Friendly Name toggle preserves nested `name.global` shape on save (no flat preset leak)", async () => {
    const user = userEvent.setup();
    wrap();
    await screen.findByRole("heading", { name: /Friendly Name/i });

    // Toggle the Friendly Name starts-with switch. The entity-side label
    // is verbose: "Starts with device name (or room if standalone)".
    const startsSwitches = await screen.findAllByRole("switch", {
      name: /starts with device name/i,
    });
    // First occurrence is inside the Friendly Name accordion panel.
    await user.click(startsSwitches[0]);

    await user.click(screen.getByRole("button", { name: /Save/i }));
    await waitFor(() => {
      const put = (globalThis.fetch as any).mock.calls.find(
        (c: any[]) => (c[0] as Request).method === "PUT",
      );
      expect(put).toBeDefined();
    });
    const put = (globalThis.fetch as any).mock.calls.find(
      (c: any[]) => (c[0] as Request).method === "PUT",
    )[0] as Request;
    const body = await put.json();
    const policy = body.policies.find(
      (p: any) => p.type === "entity_naming_convention",
    );
    // Nested shape preserved: name.global.preset, not name.preset.
    expect(policy.name.global.preset).toBe("title-case");
    expect(policy.name).not.toHaveProperty("preset");
    // Toggle reached the payload.
    expect(policy.name.starts_with_room).toBe(true);
  });
});
