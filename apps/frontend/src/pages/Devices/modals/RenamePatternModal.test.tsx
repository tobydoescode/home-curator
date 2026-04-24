import "@testing-library/jest-dom/vitest";
import { MantineProvider } from "@mantine/core";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { RenamePatternModal } from "./RenamePatternModal";

const mutateAsync = vi.fn();

vi.mock("@/hooks/useActions", () => ({
  useRenamePattern: () => ({ mutateAsync, isPending: false }),
}));

function renderModal(onClose = vi.fn()) {
  render(
    <MantineProvider>
      <RenamePatternModal deviceIds={["dev-1", "dev-2"]} onClose={onClose} />
    </MantineProvider>,
  );
  return onClose;
}

describe("RenamePatternModal", () => {
  beforeEach(() => mutateAsync.mockReset());

  it("previews matching and nonmatching device rows", async () => {
    mutateAsync.mockResolvedValue({
      results: [
        { device_id: "dev-1", matched: true, new_name: "New Name" },
        { device_id: "dev-2", matched: false },
      ],
    });
    renderModal();

    await userEvent.type(screen.getByLabelText("Pattern (Regex)"), "^Old");
    await userEvent.type(screen.getByLabelText("Replacement"), "New");
    await userEvent.click(screen.getByRole("button", { name: "Preview" }));

    expect(mutateAsync).toHaveBeenCalledWith({
      device_ids: ["dev-1", "dev-2"],
      pattern: "^Old",
      replacement: "New",
      dry_run: true,
    });
    await waitFor(() => expect(screen.getAllByText("New Name")).toHaveLength(2));
    expect(screen.getByText("1 device will be renamed.")).toBeInTheDocument();
  });

  it("applies changes only after a matching preview", async () => {
    const onClose = renderModal();
    mutateAsync.mockResolvedValueOnce({
      results: [{ device_id: "dev-1", matched: true, new_name: "New Name" }],
    });
    mutateAsync.mockResolvedValueOnce({
      results: [{ device_id: "dev-1", matched: true, ok: true }],
    });

    await userEvent.type(screen.getByLabelText("Pattern (Regex)"), "^Old");
    await userEvent.type(screen.getByLabelText("Replacement"), "New");
    await userEvent.click(screen.getByRole("button", { name: "Preview" }));
    await waitFor(() => expect(screen.getAllByText("New Name")).toHaveLength(2));
    await userEvent.click(screen.getByRole("button", { name: "Apply Rename" }));

    expect(mutateAsync).toHaveBeenLastCalledWith({
      device_ids: ["dev-1", "dev-2"],
      pattern: "^Old",
      replacement: "New",
      dry_run: false,
    });
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
