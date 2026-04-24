import { MantineProvider } from "@mantine/core";
import { Notifications } from "@mantine/notifications";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ExceptionsPage } from "./ExceptionsPage";

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <MantineProvider>
      <Notifications />
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={["/settings/exceptions"]}>
          <Routes>
            <Route
              path="/settings/exceptions"
              element={<ExceptionsPage />}
            />
            <Route path="/devices" element={<div>device page</div>} />
            <Route path="/entities" element={<div>entity page</div>} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    </MantineProvider>,
  );
}

describe("ExceptionsPage", () => {
  beforeEach(() => {
    const rows = [
      {
        id: 1,
        target_kind: "device",
        device_id: "d1",
        entity_id: null,
        target_name: "Kitchen Lamp",
        target_area_name: "Kitchen",
        device_name: "Kitchen Lamp",
        device_area_name: "Kitchen",
        policy_id: "mr",
        policy_name: "Missing Room",
        acknowledged_at: "2026-04-22T00:00:00Z",
        note: null,
      },
      {
        id: 2,
        target_kind: "entity",
        device_id: null,
        entity_id: "light.kitchen_lamp",
        target_name: "Kitchen Lamp",
        target_area_name: "Kitchen",
        policy_id: "en",
        policy_name: "Entity Naming",
        acknowledged_at: "2026-04-22T00:00:00Z",
        note: null,
      },
    ];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (req: Request) => {
        const url = typeof req === "string" ? req : req.url;
        const method = typeof req === "string" ? "GET" : req.method;
        if (method === "POST" && url.includes("/api/exceptions/bulk-delete")) {
          const body = await (req as Request).json();
          return new Response(JSON.stringify({ deleted: body.ids }), {
            status: 200,
          });
        }
        if (url.includes("/api/exceptions/list")) {
          return new Response(
            JSON.stringify({
              exceptions: rows,
              total: 2,
              page: 1,
              page_size: 50,
            }),
            { status: 200 },
          );
        }
        return new Response("{}", { status: 200 });
      }),
    );
  });

  it("renders a Target column with a badge per kind", async () => {
    wrap();
    await waitFor(() =>
      expect(screen.getByText("Missing Room")).toBeInTheDocument(),
    );
    expect(screen.getByText(/^device$/i)).toBeInTheDocument();
    expect(screen.getByText(/^entity$/i)).toBeInTheDocument();
  });

  it("row click routes to /devices?device= for a device row", async () => {
    const user = userEvent.setup();
    wrap();
    await waitFor(() =>
      expect(screen.getByText("Missing Room")).toBeInTheDocument(),
    );
    const deviceRow = screen
      .getAllByText("Kitchen Lamp")[0]
      .closest("tr") as HTMLElement;
    await user.click(deviceRow);
    expect(await screen.findByText("device page")).toBeInTheDocument();
  });

  it("row click routes to /entities?entity= for an entity row", async () => {
    const user = userEvent.setup();
    wrap();
    await waitFor(() =>
      expect(screen.getByText("Entity Naming")).toBeInTheDocument(),
    );
    const entityRow = screen
      .getByText("Entity Naming")
      .closest("tr") as HTMLElement;
    await user.click(entityRow);
    expect(await screen.findByText("entity page")).toBeInTheDocument();
  });

  it("renders rows and bulk-deletes selected ones", async () => {
    const user = userEvent.setup();
    wrap();
    await waitFor(() =>
      expect(screen.getByText("Missing Room")).toBeInTheDocument(),
    );
    const cbs = screen.getAllByRole("checkbox");
    await user.click(cbs[0]);
    await user.click(screen.getByRole("button", { name: /remove selected/i }));
    await waitFor(() => {
      const calls = (globalThis.fetch as any).mock.calls;
      const bulkCall = calls.find((c: any[]) => {
        const url = typeof c[0] === "string" ? c[0] : c[0].url;
        return url.includes("/api/exceptions/bulk-delete");
      });
      expect(bulkCall).toBeDefined();
    });
  });

  it("shows an empty state when total is 0", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              exceptions: [],
              total: 0,
              page: 1,
              page_size: 50,
            }),
            { status: 200 },
          ),
      ),
    );
    wrap();
    await waitFor(() =>
      expect(screen.getByText(/no exceptions yet/i)).toBeInTheDocument(),
    );
  });
});
