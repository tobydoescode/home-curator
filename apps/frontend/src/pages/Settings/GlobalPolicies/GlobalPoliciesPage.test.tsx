import { MantineProvider } from "@mantine/core";
import { ModalsProvider } from "@mantine/modals";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

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
  beforeEach(() => {
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
    vi.stubGlobal("fetch", vi.fn(async (req: Request) => {
      const url = typeof req === "string" ? req : req.url;
      if (url.endsWith("/api/policies/file")) {
        return new Response(JSON.stringify({
          version: 1,
          policies: [
            {
              id: "aqara-needs-room", type: "custom", scope: "devices",
              enabled: true, severity: "info", when: "true", assert: "true", message: "m",
            },
            { id: "nc", type: "naming_convention", enabled: true, severity: "warning", global: { preset: "snake_case" }, starts_with_room: false, rooms: [] },
          ],
        }), { status: 200 });
      }
      return new Response("{}", { status: 200 });
    }));
  });

  it("lists only custom policies in the left pane", async () => {
    wrap();
    await waitFor(() => {
      expect(screen.getByText("aqara-needs-room")).toBeInTheDocument();
    });
    expect(screen.queryByText("nc")).not.toBeInTheDocument();
  });
});
