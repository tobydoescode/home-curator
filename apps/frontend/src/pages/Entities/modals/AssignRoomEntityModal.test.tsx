import "@testing-library/jest-dom/vitest";
import { MantineProvider } from "@mantine/core";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AssignRoomEntityModal } from "./AssignRoomEntityModal";

const mutateAsync = vi.fn();

vi.mock("@/hooks/useEntityActions", () => ({
  useAssignRoomEntities: () => ({ mutateAsync, isPending: false }),
}));

function renderModal(onClose = vi.fn()) {
  render(
    <MantineProvider>
      <AssignRoomEntityModal
        entityIds={["light.kitchen", "sensor.temp"]}
        rooms={[{ id: "kitchen", name: "Kitchen" }]}
        onClose={onClose}
      />
    </MantineProvider>,
  );
  return onClose;
}

describe("AssignRoomEntityModal", () => {
  beforeEach(() => mutateAsync.mockReset());

  it("keeps Assign disabled until a room is selected", async () => {
    renderModal();

    expect(screen.getByRole("button", { name: "Assign" })).toBeDisabled();
    await userEvent.click(screen.getByRole("textbox", { name: "Room" }));
    await userEvent.click(screen.getByText("Kitchen"));

    expect(screen.getByRole("button", { name: "Assign" })).toBeEnabled();
  });

  it("assigns selected room to all entities and closes", async () => {
    mutateAsync.mockResolvedValue({});
    const onClose = renderModal();

    await userEvent.click(screen.getByRole("textbox", { name: "Room" }));
    await userEvent.click(screen.getByText("Kitchen"));
    await userEvent.click(screen.getByRole("button", { name: "Assign" }));

    expect(mutateAsync).toHaveBeenCalledWith({
      entity_ids: ["light.kitchen", "sensor.temp"],
      area_id: "kitchen",
    });
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
