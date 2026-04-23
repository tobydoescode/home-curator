import "@testing-library/jest-dom/vitest";

import { MantineProvider } from "@mantine/core";
import { Notifications } from "@mantine/notifications";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { showDetailedResultToast } from "./useDetailedToast";

function wrap(ui: React.ReactElement) {
  return (
    <MantineProvider>
      <Notifications />
      {ui}
    </MantineProvider>
  );
}

describe("showDetailedResultToast", () => {
  it("all-ok → green, singular copy for 1 result, no details", async () => {
    render(wrap(<div />));
    showDetailedResultToast({
      kind: "Entity",
      action: "Deleted",
      results: [{ id: "light.a", ok: true }],
    });
    expect(await screen.findByText("Entity Deleted")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /view details/i }),
    ).not.toBeInTheDocument();
  });

  it("all-ok → green, plural copy for >1 result", async () => {
    render(wrap(<div />));
    showDetailedResultToast({
      kind: "Entity",
      action: "Deleted",
      results: [
        { id: "light.a", ok: true },
        { id: "light.b", ok: true },
      ],
    });
    expect(await screen.findByText("2 Entities Deleted")).toBeInTheDocument();
  });

  it("partial → yellow with 'View Details' opening a per-row popover", async () => {
    const user = userEvent.setup();
    render(wrap(<div />));
    showDetailedResultToast({
      kind: "Entity",
      action: "Deleted",
      results: [
        { id: "light.a", ok: true },
        { id: "light.b", ok: false, error: "integration refused" },
      ],
    });
    const detailsBtn = await screen.findByRole("button", {
      name: /view details/i,
    });
    await user.click(detailsBtn);
    expect(await screen.findByText("light.b")).toBeInTheDocument();
    expect(screen.getByText(/integration refused/i)).toBeInTheDocument();
  });

  it("all-fail → red with first error as message", async () => {
    render(wrap(<div />));
    showDetailedResultToast({
      kind: "Entity",
      action: "Deleted",
      results: [{ id: "light.a", ok: false, error: "nope" }],
    });
    expect(await screen.findByText(/nope/i)).toBeInTheDocument();
  });
});
