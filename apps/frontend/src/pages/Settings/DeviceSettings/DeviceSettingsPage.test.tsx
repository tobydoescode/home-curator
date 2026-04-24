import { MantineProvider } from "@mantine/core";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DeviceSettingsPage } from "./DeviceSettingsPage";

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <MantineProvider>
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <DeviceSettingsPage />
        </MemoryRouter>
      </QueryClientProvider>
    </MantineProvider>,
  );
}

describe("DeviceSettingsPage", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(async (req: Request) => {
      const url = typeof req === "string" ? req : req.url;
      if (url.endsWith("/api/policies/file")) {
        return new Response(JSON.stringify({
          version: 1,
          policies: [
            {
              id: "nc", type: "naming_convention", enabled: true, severity: "warning",
              global: { preset: "snake_case" }, starts_with_room: false, rooms: [],
            },
            { id: "mr", type: "missing_area", enabled: true, severity: "warning" },
          ],
        }), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      if (url.includes("/api/areas")) {
        return new Response(JSON.stringify([]), { status: 200 });
      }
      return new Response("{}", { status: 200 });
    }));
  });

  it("renders the three sections", async () => {
    wrap();
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Naming" })).toBeInTheDocument();
    });
    expect(screen.getByRole("heading", { name: "Built-In Rules" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Custom Rules" })).toBeInTheDocument();
  });
});
