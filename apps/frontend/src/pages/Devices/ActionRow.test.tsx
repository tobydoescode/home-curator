import "@testing-library/jest-dom/vitest";

import { MantineProvider } from "@mantine/core";
import { ModalsProvider } from "@mantine/modals";
import { Notifications } from "@mantine/notifications";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ActionRow } from "./ActionRow";
import type { DeviceRow } from "./DevicesTable";

afterEach(() => {
  vi.restoreAllMocks();
});

const DEVICE: DeviceRow = {
  id: "d1",
  name: "Lamp",
  area_name: "Living Room",
  integration: "hue",
  created_at: null,
  modified_at: null,
  issue_count: 0,
  highest_severity: null,
};

const ROOMS = [{ id: "living", name: "Living Room" }];

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  // Mirror the real App provider order: QueryClientProvider must wrap
  // ModalsProvider so modal-rendered children (which live inside
  // ModalsProvider's own subtree) can still see the React Query context.
  return (
    <MantineProvider>
      <Notifications />
      <QueryClientProvider client={qc}>
        <ModalsProvider>{ui}</ModalsProvider>
      </QueryClientProvider>
    </MantineProvider>
  );
}

describe("ActionRow", () => {
  it("opens the Assign Room modal when Assign Room is clicked", async () => {
    const user = userEvent.setup();
    render(
      wrap(
        <ActionRow
          selectedIds={["d1"]}
          rooms={ROOMS}
          deviceLookup={{ d1: DEVICE }}
        />,
      ),
    );

    await user.click(screen.getByRole("button", { name: /Assign Room/i }));

    expect(await screen.findByText(/Assigning a room to/i)).toBeInTheDocument();
  });

  it("opens the Rename modal via the More menu", async () => {
    const user = userEvent.setup();
    render(
      wrap(
        <ActionRow
          selectedIds={["d1"]}
          rooms={ROOMS}
          deviceLookup={{ d1: DEVICE }}
        />,
      ),
    );

    await user.click(screen.getByRole("button", { name: /More/i }));
    const renameItem = await screen.findByRole("menuitem", {
      name: /^Rename…$/,
    });
    await user.click(renameItem);

    // Modal title proves the Rename modal was opened
    expect(
      await screen.findByRole("heading", { name: "Rename Device" }),
    ).toBeInTheDocument();
    const nameInput = (await screen.findByLabelText(/Name/)) as HTMLInputElement;
    expect(nameInput.value).toBe("Lamp");
  });

  it("opens the Rename (Pattern) modal via the More menu", async () => {
    const user = userEvent.setup();
    render(
      wrap(
        <ActionRow
          selectedIds={["d1"]}
          rooms={ROOMS}
          deviceLookup={{ d1: DEVICE }}
        />,
      ),
    );

    await user.click(screen.getByRole("button", { name: /More/i }));
    await user.click(
      await screen.findByRole("menuitem", { name: /Rename \(Pattern\)…/ }),
    );

    expect(await screen.findByLabelText(/Pattern \(Regex\)/i)).toBeInTheDocument();
  });
});
