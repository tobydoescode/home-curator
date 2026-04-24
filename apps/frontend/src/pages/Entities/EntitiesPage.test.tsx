import "@testing-library/jest-dom/vitest";

import { MantineProvider } from "@mantine/core";
import { ModalsProvider } from "@mantine/modals";
import { Notifications } from "@mantine/notifications";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { EntitiesPage } from "./EntitiesPage";

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
  window.localStorage.clear();
});

const ENTITY = {
  entity_id: "light.kitchen_lamp",
  name: "Kitchen Lamp",
  original_name: null,
  display_name: "Kitchen Lamp",
  domain: "light",
  platform: "hue",
  device_id: "d1",
  device_name: "Hue Bulb",
  area_id: "kitchen",
  area_name: "Kitchen",
  disabled_by: null,
  hidden_by: null,
  icon: null,
  created_at: null,
  modified_at: null,
  issue_count: 0,
  highest_severity: null,
  issues: [],
};

function mockEntities(overrides: Record<string, unknown> = {}) {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify({
        entities: [ENTITY],
        total: 1,
        page: 1,
        page_size: 50,
        issue_counts_by_type: {},
        domain_counts: { light: 1 },
        area_counts: { Kitchen: 1 },
        integration_counts: { hue: 1 },
        all_domains: ["light"],
        all_areas: [{ id: "kitchen", name: "Kitchen" }],
        all_integrations: ["hue"],
        all_issue_types: [],
        ...overrides,
      }),
      { status: 200, headers: { "content-type": "application/json" } },
    ),
  );
}

function wrap(initialEntries: string[] = ["/entities"]) {
  const qc = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return (
    <MantineProvider>
      <Notifications />
      <QueryClientProvider client={qc}>
        <ModalsProvider>
          <MemoryRouter initialEntries={initialEntries}>
            <EntitiesPage />
          </MemoryRouter>
        </ModalsProvider>
      </QueryClientProvider>
    </MantineProvider>
  );
}

describe("EntitiesPage", () => {
  it("renders a row per entity and shows the total", async () => {
    mockEntities();
    render(wrap());
    await waitFor(() =>
      expect(screen.getByText("light.kitchen_lamp")).toBeInTheDocument(),
    );
    expect(screen.getByText(/1 entities/i)).toBeInTheDocument();
  });

  it("hydrates filters from URL search params on first render", async () => {
    const fetchSpy = mockEntities();
    render(wrap(["/entities?q=lamp&with_issues=true&domain=light"]));
    await waitFor(() => expect(fetchSpy).toHaveBeenCalled());
    const url = (fetchSpy.mock.calls[0][0] as Request).url;
    expect(url).toContain("q=lamp");
    expect(url).toContain("with_issues=true");
    expect(url).toContain("domain=light");
  });

  it("typing in the search input drives the q param after debounce", async () => {
    const fetchSpy = mockEntities();
    const { default: userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    render(wrap());
    // Wait for loading to resolve so the FilterBar input is mounted.
    await waitFor(() =>
      expect(screen.getByText("light.kitchen_lamp")).toBeInTheDocument(),
    );

    await user.type(screen.getByPlaceholderText(/Search Entity ID/i), "lamp");
    await waitFor(
      () => {
        const lastUrl = (fetchSpy.mock.calls.at(-1)![0] as Request).url;
        expect(lastUrl).toContain("q=lamp");
      },
      { timeout: 800 },
    );
  });

  it("ActionRow shows only when ≥1 row is selected", async () => {
    mockEntities();
    const { default: userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    render(wrap());

    await waitFor(() =>
      expect(screen.getByText("light.kitchen_lamp")).toBeInTheDocument(),
    );
    expect(screen.queryByText(/Selected/i)).not.toBeInTheDocument();

    await user.click(screen.getByLabelText(/^Select Kitchen Lamp$/i));
    expect(await screen.findByText(/1 Entity Selected/i)).toBeInTheDocument();
  });

  it("clicking a sort header updates URL params and resets to page 1", async () => {
    const fetchSpy = mockEntities({ total: 200 });
    const { default: userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    render(wrap(["/entities?page=3"]));
    // Wait for the table to render so the sort header button is present.
    await waitFor(() =>
      expect(screen.getByText("light.kitchen_lamp")).toBeInTheDocument(),
    );
    fetchSpy.mockClear();

    await user.click(screen.getByRole("button", { name: /Sort by Entity ID/i }));
    await waitFor(() => {
      const url = (fetchSpy.mock.calls.at(-1)![0] as Request).url;
      expect(url).toContain("sort_by=entity_id");
      expect(url).toContain("sort_dir=asc");
      expect(url).toContain("page=1");
    });
  });

  it("column-visibility gear toggles persist in localStorage scoped to entities", async () => {
    mockEntities();
    const { default: userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    render(wrap());

    await waitFor(() =>
      expect(screen.getByText("light.kitchen_lamp")).toBeInTheDocument(),
    );
    // Integration column hidden by default → no header.
    expect(
      screen.queryByRole("button", { name: /Sort by Integration/i }),
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Columns/i }));
    await user.click(
      await screen.findByRole("checkbox", { name: "Integration" }),
    );

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /Sort by Integration/i }),
      ).toBeInTheDocument(),
    );
    expect(
      window.localStorage.getItem("home-curator:columns:entities"),
    ).not.toBeNull();
    // Devices key must be untouched.
    expect(
      window.localStorage.getItem("home-curator:columns:devices"),
    ).toBeNull();
  });

  it("row click opens the drawer, close button stays closed (no reopen loop)", async () => {
    mockEntities();
    const { default: userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    render(wrap());

    await waitFor(() =>
      expect(screen.getByText("light.kitchen_lamp")).toBeInTheDocument(),
    );

    // Open: row click.
    await user.click(screen.getByText("light.kitchen_lamp"));
    const idInput = (await screen.findByLabelText(
      "Entity ID",
    )) as HTMLInputElement;
    // Drawer's Entity ID input holds only the object_id portion; the
    // domain is shown as a readonly leftSection.
    expect(idInput.value).toBe("kitchen_lamp");

    // Close via the drawer's Cancel button (form is pristine so no dirty-guard).
    await user.click(screen.getByRole("button", { name: /^Cancel$/ }));

    // Drawer must stay closed — previously a dual-effect race immediately
    // re-synced the URL param back into drawer state, reopening it.
    await waitFor(() =>
      expect(screen.queryByLabelText("Entity ID")).not.toBeInTheDocument(),
    );
  });
});
