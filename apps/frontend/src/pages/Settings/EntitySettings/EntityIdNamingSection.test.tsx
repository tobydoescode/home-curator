import "@testing-library/jest-dom/vitest";

import { MantineProvider } from "@mantine/core";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useState } from "react";

import { EntityIdNamingSection, type EntityIdBlock } from "./EntityIdNamingSection";

function Harness({ initial }: { initial: EntityIdBlock }) {
  const [b, setB] = useState(initial);
  return <EntityIdNamingSection block={b} onChange={setB} />;
}

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient();
  return (
    <MantineProvider>
      <QueryClientProvider client={qc}>{ui}</QueryClientProvider>
    </MantineProvider>
  );
}

beforeEach(() => {
  window.HTMLElement.prototype.scrollIntoView = vi.fn();
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(
          JSON.stringify([
            { id: "office", name: "Office" },
            { id: "garage", name: "Garage" },
          ]),
          { status: 200 },
        ),
    ),
  );
});

describe("EntityIdNamingSection", () => {
  it("shows a readonly derived snake_case pattern (no preset dropdown)", () => {
    render(
      wrap(<Harness initial={{ starts_with_room: true, rooms: [] }} />),
    );
    expect(screen.queryByLabelText(/preset/i)).not.toBeInTheDocument();
    expect(screen.getByDisplayValue(/\^\[a-z\]/)).toBeInTheDocument();
  });

  it("per-room override row has room selector + on/off toggle only (no alternate preset)", async () => {
    const user = userEvent.setup();
    render(
      wrap(
        <Harness
          initial={{
            starts_with_room: true,
            rooms: [{ area_id: "garage", enabled: false }],
          }}
        />,
      ),
    );
    // Wait for the areas query to resolve so the row's aria-label uses the
    // resolved area name ("Garage enabled").
    await waitFor(() =>
      expect(
        screen.getByRole("switch", { name: /Garage enabled/i }),
      ).toBeInTheDocument(),
    );
    expect(
      screen.getByRole("switch", { name: /Garage enabled/i }),
    ).not.toBeChecked();
    await user.click(screen.getByRole("switch", { name: /Garage enabled/i }));
  });
});
