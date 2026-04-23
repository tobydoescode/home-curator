import "@testing-library/jest-dom/vitest";

import { MantineProvider } from "@mantine/core";
import { ModalsProvider } from "@mantine/modals";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { openRenameConfirmModal } from "./RenameConfirmModal";

function wrap(ui: React.ReactElement) {
  return (
    <MantineProvider>
      <ModalsProvider>{ui}</ModalsProvider>
    </MantineProvider>
  );
}

function Trigger({ onConfirm }: { onConfirm: () => void }) {
  return (
    <button
      type="button"
      onClick={() =>
        openRenameConfirmModal({
          oldId: "light.kitchen_lamp",
          newId: "light.study_lamp",
          onConfirm,
        })
      }
    >
      open
    </button>
  );
}

describe("RenameConfirmModal", () => {
  it("renders title, old → new id, and 'NOT automatically updated' checklist", async () => {
    const user = userEvent.setup();
    render(wrap(<Trigger onConfirm={() => {}} />));
    await user.click(screen.getByRole("button", { name: /open/i }));
    expect(await screen.findByText(/Rename Entity ID\?/i)).toBeInTheDocument();
    expect(screen.getByText(/light\.kitchen_lamp/)).toBeInTheDocument();
    expect(screen.getByText(/light\.study_lamp/)).toBeInTheDocument();
    expect(screen.getByText(/Template entities/)).toBeInTheDocument();
    expect(screen.getByText(/Lovelace dashboards/)).toBeInTheDocument();
    expect(screen.getByText(/Spook/)).toBeInTheDocument();
  });

  it("Rename button fires onConfirm; Keep does nothing", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(wrap(<Trigger onConfirm={onConfirm} />));
    await user.click(screen.getByRole("button", { name: /open/i }));
    await user.click(await screen.findByRole("button", { name: /Keep/i }));
    expect(onConfirm).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: /open/i }));
    await user.click(await screen.findByRole("button", { name: /Rename/i }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });
});
