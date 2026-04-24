import { MantineProvider } from "@mantine/core";
import { ModalsProvider } from "@mantine/modals";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { GlobalPoliciesPage } from "./GlobalPoliciesPage";

function wrap(path = "/settings/global") {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <MantineProvider>
      <ModalsProvider>
        <QueryClientProvider client={qc}>
          <MemoryRouter initialEntries={[path]}>
            <GlobalPoliciesPage />
          </MemoryRouter>
        </QueryClientProvider>
      </ModalsProvider>
    </MantineProvider>,
  );
}

describe("GlobalPoliciesPage", () => {
  const policiesFile = {
    version: 1,
    policies: [
      {
        id: "aqara-needs-room",
        type: "custom",
        scope: "devices",
        enabled: true,
        severity: "info",
        when: "true",
        assert: "true",
        message: "m",
      },
      {
        id: "nc",
        type: "naming_convention",
        enabled: true,
        severity: "warning",
        global: { preset: "snake_case" },
        starts_with_room: false,
        rooms: [],
      },
    ],
  };

  beforeEach(() => {
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
    vi.stubGlobal("fetch", vi.fn(async (req: Request) => {
      const url = typeof req === "string" ? req : req.url;
      if (url.endsWith("/api/policies/file")) {
        return new Response(JSON.stringify(policiesFile), { status: 200 });
      }
      if (url.endsWith("/api/policies/simulate")) {
        return new Response(JSON.stringify({ results: [] }), { status: 200 });
      }
      if (url.endsWith("/api/policies")) {
        return new Response(JSON.stringify({ ok: true }), { status: 200 });
      }
      return new Response("{}", { status: 200 });
    }));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("lists only custom policies in the left pane", async () => {
    wrap();
    await waitFor(() => {
      expect(screen.getByText("aqara-needs-room")).toBeInTheDocument();
    });
    expect(screen.queryByText("nc")).not.toBeInTheDocument();
  });

  it("auto-runs simulation from the test query parameter", async () => {
    wrap("/settings/global?test=aqara-needs-room");

    await waitFor(() => {
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        expect.objectContaining({
          url: expect.stringContaining("/api/policies/simulate"),
        }),
      );
    });
    const simulateRequest = vi
      .mocked(fetch)
      .mock.calls.map(([req]) => req)
      .find((req) => req instanceof Request && req.url.endsWith("/api/policies/simulate"));
    expect(await (simulateRequest as Request).json()).toEqual({
      policy_id: "aqara-needs-room",
    });
  });

  it("runs simulation for a listed custom policy", async () => {
    wrap();
    await screen.findByText("aqara-needs-room");

    await userEvent.click(screen.getByRole("button", { name: "Test" }));

    await waitFor(() => {
      expect(
        vi
          .mocked(fetch)
          .mock.calls.some(
            ([req]) => req instanceof Request && req.url.endsWith("/api/policies/simulate"),
          ),
      ).toBe(true);
    });
  });

  it("saves the current draft", async () => {
    wrap();
    await screen.findByText("aqara-needs-room");

    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(
        vi
          .mocked(fetch)
          .mock.calls.some(
            ([req]) =>
              req instanceof Request &&
              req.url.endsWith("/api/policies") &&
              req.method === "PUT",
          ),
      ).toBe(true);
    });
  });
});
