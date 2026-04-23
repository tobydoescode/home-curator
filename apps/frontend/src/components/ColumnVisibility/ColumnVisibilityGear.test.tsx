import "@testing-library/jest-dom/vitest";

import { MantineProvider } from "@mantine/core";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ColumnVisibilityGear } from "./ColumnVisibilityGear";

const COLUMNS = [
  { id: "name", label: "Name" },
  { id: "room", label: "Room" },
  { id: "modified", label: "Modified" },
];

function wrap(ui: React.ReactElement) {
  return <MantineProvider>{ui}</MantineProvider>;
}

describe("ColumnVisibilityGear", () => {
  it("renders the gear icon button", () => {
    render(
      wrap(
        <ColumnVisibilityGear
          columns={COLUMNS}
          visible={{ name: true, room: true, modified: false }}
          onToggle={() => {}}
          onReset={() => {}}
        />,
      ),
    );
    expect(screen.getByRole("button", { name: /Columns/i })).toBeInTheDocument();
  });

  it("opens a popover with one checkbox per column when clicked", async () => {
    const user = userEvent.setup();
    render(
      wrap(
        <ColumnVisibilityGear
          columns={COLUMNS}
          visible={{ name: true, room: true, modified: false }}
          onToggle={() => {}}
          onReset={() => {}}
        />,
      ),
    );
    await user.click(screen.getByRole("button", { name: /Columns/i }));
    const nameBox = await screen.findByRole("checkbox", { name: "Name" });
    const roomBox = screen.getByRole("checkbox", { name: "Room" });
    const modBox = screen.getByRole("checkbox", { name: "Modified" });
    expect(nameBox).toBeChecked();
    expect(roomBox).toBeChecked();
    expect(modBox).not.toBeChecked();
  });

  it("calls onToggle with the column id when a checkbox is clicked", async () => {
    const onToggle = vi.fn();
    const user = userEvent.setup();
    render(
      wrap(
        <ColumnVisibilityGear
          columns={COLUMNS}
          visible={{ name: true, room: true, modified: false }}
          onToggle={onToggle}
          onReset={() => {}}
        />,
      ),
    );
    await user.click(screen.getByRole("button", { name: /Columns/i }));
    await user.click(await screen.findByRole("checkbox", { name: "Modified" }));
    expect(onToggle).toHaveBeenCalledWith("modified");
  });

  it("calls onReset when the Reset to defaults button is clicked", async () => {
    const onReset = vi.fn();
    const user = userEvent.setup();
    render(
      wrap(
        <ColumnVisibilityGear
          columns={COLUMNS}
          visible={{ name: true, room: true, modified: false }}
          onToggle={() => {}}
          onReset={onReset}
        />,
      ),
    );
    await user.click(screen.getByRole("button", { name: /Columns/i }));
    await user.click(
      await screen.findByRole("button", { name: /Reset to defaults/i }),
    );
    expect(onReset).toHaveBeenCalledTimes(1);
  });
});
