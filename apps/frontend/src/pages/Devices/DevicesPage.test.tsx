import { MantineProvider } from "@mantine/core";
import { ModalsProvider } from "@mantine/modals";
import { Notifications } from "@mantine/notifications";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DevicesPage } from "./DevicesPage";

afterEach(() => {
  vi.restoreAllMocks();
});

function mockFetchOnce(body: unknown) {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify(body), {
      status: 200,
      headers: { "content-type": "application/json" },
    }),
  );
}

function wrap(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  // Provider order mirrors App.tsx. ModalsProvider MUST be a descendant of
  // QueryClientProvider — modal children render inside ModalsProvider's
  // subtree and otherwise can't call `useQueryClient()`.
  return (
    <MantineProvider>
      <Notifications />
      <QueryClientProvider client={client}>
        <ModalsProvider>
          <MemoryRouter>{ui}</MemoryRouter>
        </ModalsProvider>
      </QueryClientProvider>
    </MantineProvider>
  );
}

describe("DevicesPage", () => {
  it("renders a row for each device", async () => {
    mockFetchOnce({
      devices: [
        {
          id: "d1",
          name: "Lamp",
          manufacturer: null,
          model: null,
          area_id: "living",
          area_name: "Living Room",
          integration: "hue",
          disabled_by: null,
          entities: [],
          issue_count: 0,
          highest_severity: null,
          issues: [],
        },
      ],
      total: 1,
      page: 1,
      page_size: 50,
      issue_counts_by_type: {},
    });
    render(wrap(<DevicesPage />));
    await waitFor(() =>
      expect(screen.getByText("Lamp")).toBeInTheDocument(),
    );
    // "Living Room" appears both in the row and the Room filter options.
    expect(screen.getAllByText("Living Room").length).toBeGreaterThan(0);
  });

  it("opens the edit drawer when a row is clicked", async () => {
    mockFetchOnce({
      devices: [
        {
          id: "d1",
          name: "Lamp",
          name_by_user: null,
          manufacturer: null,
          model: null,
          area_id: "living",
          area_name: "Living Room",
          integration: "hue",
          disabled_by: null,
          entities: [],
          issue_count: 0,
          highest_severity: null,
          issues: [],
        },
      ],
      total: 1,
      page: 1,
      page_size: 50,
      issue_counts_by_type: {},
      all_areas: [{ id: "living", name: "Living Room" }],
      all_issue_types: [],
      all_integrations: [],
      area_counts: {},
      integration_counts: {},
    });
    const { default: userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    render(wrap(<DevicesPage />));
    await waitFor(() => expect(screen.getByText("Lamp")).toBeInTheDocument());
    await user.click(screen.getByText("Lamp"));
    const nameInput = (await screen.findByLabelText("Name")) as HTMLInputElement;
    expect(nameInput.value).toBe("Lamp");
  });
});
