import "@testing-library/jest-dom/vitest";

import { MantineProvider } from "@mantine/core";
import { ModalsProvider } from "@mantine/modals";
import { Notifications } from "@mantine/notifications";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { EditDeviceDrawer } from "./EditDeviceDrawer";

afterEach(() => {
  vi.restoreAllMocks();
});

const DEVICE = {
  id: "d1",
  name: "hue_bulb_3",
  name_by_user: null as string | null,
  area_id: "living",
  area_name: "Living Room",
  issues: [],
};

const AREAS = [
  { id: "living", name: "Living Room" },
  { id: "office", name: "Office" },
];

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <MantineProvider>
      <Notifications />
      <ModalsProvider>
        <QueryClientProvider client={qc}>{ui}</QueryClientProvider>
      </ModalsProvider>
    </MantineProvider>
  );
}

describe("EditDeviceDrawer", () => {
  it("seeds Name and Room from the device and disables Save when clean", () => {
    render(
      wrap(
        <EditDeviceDrawer
          opened
          onClose={() => {}}
          device={DEVICE}
          areas={AREAS}
        />,
      ),
    );
    const nameInput = screen.getByLabelText("Name") as HTMLInputElement;
    expect(nameInput.value).toBe("hue_bulb_3");
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
  });

  it("PATCHes only the changed field when Save is clicked", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    const user = userEvent.setup();
    render(
      wrap(
        <EditDeviceDrawer
          opened
          onClose={() => {}}
          device={DEVICE}
          areas={AREAS}
        />,
      ),
    );
    const nameInput = screen.getByLabelText("Name");
    await user.clear(nameInput);
    await user.type(nameInput, "Hue Bulb 3");
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const req = fetchSpy.mock.calls[0][0] as Request;
    expect(req.method).toBe("PATCH");
    expect(req.url).toContain("/api/devices/d1");
    expect(await req.json()).toEqual({ name_by_user: "Hue Bulb 3" });
  });

  it("trims the name before sending", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    const user = userEvent.setup();
    render(
      wrap(
        <EditDeviceDrawer
          opened
          onClose={() => {}}
          device={DEVICE}
          areas={AREAS}
        />,
      ),
    );
    const nameInput = screen.getByLabelText("Name");
    await user.clear(nameInput);
    await user.type(nameInput, "  Hue Bulb 3  ");
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const req = fetchSpy.mock.calls[0][0] as Request;
    expect(await req.json()).toEqual({ name_by_user: "Hue Bulb 3" });
  });

  it("triggers Save when Enter is pressed in the Name field", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    const user = userEvent.setup();
    render(
      wrap(
        <EditDeviceDrawer
          opened
          onClose={() => {}}
          device={DEVICE}
          areas={AREAS}
        />,
      ),
    );
    const nameInput = screen.getByLabelText("Name");
    await user.clear(nameInput);
    await user.type(nameInput, "Hue Bulb 3{Enter}");

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const req = fetchSpy.mock.calls[0][0] as Request;
    expect(await req.json()).toEqual({ name_by_user: "Hue Bulb 3" });
  });

  it("sends only area_id when only Room changes", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    const user = userEvent.setup();
    render(
      wrap(
        <EditDeviceDrawer
          opened
          onClose={() => {}}
          device={DEVICE}
          areas={AREAS}
        />,
      ),
    );
    const roomInput = screen
      .getAllByLabelText("Room")
      .find((el) => el.tagName === "INPUT") as HTMLElement;
    await user.click(roomInput);
    await user.click(await screen.findByRole("option", { name: "Office" }));
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const req = fetchSpy.mock.calls[0][0] as Request;
    expect(await req.json()).toEqual({ area_id: "office" });
  });

  it("prompts to discard when closing with unsaved changes", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      wrap(
        <EditDeviceDrawer
          opened
          onClose={onClose}
          device={DEVICE}
          areas={AREAS}
        />,
      ),
    );
    const nameInput = screen.getByLabelText("Name");
    await user.clear(nameInput);
    await user.type(nameInput, "dirty");
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    // Confirm dialog appears
    expect(await screen.findByText("Discard changes?")).toBeInTheDocument();

    // "Keep editing" leaves the drawer open
    await user.click(screen.getByRole("button", { name: "Keep editing" }));
    expect(onClose).not.toHaveBeenCalled();

    // Trigger close again and discard this time
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    await user.click(await screen.findByRole("button", { name: "Discard" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("keeps dirty state when Save fails", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "ha update failed" }), {
        status: 502,
        headers: { "content-type": "application/json" },
      }),
    );
    const user = userEvent.setup();
    render(
      wrap(
        <EditDeviceDrawer
          opened
          onClose={() => {}}
          device={DEVICE}
          areas={AREAS}
        />,
      ),
    );
    const nameInput = screen.getByLabelText("Name") as HTMLInputElement;
    await user.clear(nameInput);
    await user.type(nameInput, "attempted");
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(nameInput.value).toBe("attempted");
    expect(screen.getByRole("button", { name: "Save" })).not.toBeDisabled();
  });

  it("renders the issues list with Acknowledge and Clear buttons", () => {
    const deviceWithIssues = {
      ...DEVICE,
      issues: [
        {
          policy_id: "naming-convention",
          rule_type: "naming_convention",
          severity: "warning" as const,
          message: "Name doesn't match convention",
        },
      ],
    };
    render(
      wrap(
        <EditDeviceDrawer
          opened
          onClose={() => {}}
          device={deviceWithIssues}
          areas={AREAS}
        />,
      ),
    );
    expect(screen.getByText("Name doesn't match convention")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Acknowledge As Exception/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Clear Exception/i }),
    ).toBeInTheDocument();
  });

  it("re-reads as non-dirty when the device prop updates to the saved value", async () => {
    // Regression guard: initialName / initialAreaId are recomputed each
    // render from the device prop. After a save lands and the parent
    // refetches, the drawer sees new props where name_by_user matches
    // what the user just saved — isDirty must flip back to false so the
    // Save button disables without any manual reset.
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    const user = userEvent.setup();
    const { rerender } = render(
      wrap(
        <EditDeviceDrawer
          opened
          onClose={() => {}}
          device={DEVICE}
          areas={AREAS}
        />,
      ),
    );
    const nameInput = screen.getByLabelText("Name") as HTMLInputElement;
    await user.clear(nameInput);
    await user.type(nameInput, "Hue Bulb 3");
    await user.click(screen.getByRole("button", { name: "Save" }));

    // Simulate the parent re-rendering with the post-save server state.
    rerender(
      wrap(
        <EditDeviceDrawer
          opened
          onClose={() => {}}
          device={{ ...DEVICE, name_by_user: "Hue Bulb 3" }}
          areas={AREAS}
        />,
      ),
    );

    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
  });

  it("deletes the device via confirm modal and closes on success", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ results: [{ device_id: "d1", ok: true }] }),
        { status: 200, headers: { "content-type": "application/json" } },
      ),
    );
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      wrap(
        <EditDeviceDrawer
          opened
          onClose={onClose}
          device={DEVICE}
          areas={AREAS}
        />,
      ),
    );
    await user.click(screen.getByRole("button", { name: "Delete" }));

    // Confirm modal appears with the device's display name.
    expect(await screen.findByText(/Delete hue_bulb_3\?/i)).toBeInTheDocument();

    // "Keep" leaves everything alone.
    await user.click(screen.getByRole("button", { name: "Keep" }));
    expect(onClose).not.toHaveBeenCalled();

    // Wait for the confirm modal to fully unmount before re-opening.
    await waitFor(() =>
      expect(screen.queryByText(/Delete hue_bulb_3\?/i)).not.toBeInTheDocument(),
    );

    // Re-open and confirm delete. Drawer's Delete button is the only one now.
    await user.click(screen.getByRole("button", { name: "Delete" }));
    // Scope to the confirm modal (its heading contains the device name).
    const confirmTitle = await screen.findByText(/Delete hue_bulb_3\?/i);
    const modalRoot = confirmTitle.closest('[role="dialog"]') as HTMLElement;
    await user.click(within(modalRoot).getByRole("button", { name: "Delete" }));

    // The POST fired with a single-id payload.
    const deletePost = fetchSpy.mock.calls
      .map((c) => c[0] as Request)
      .find((r) => r.url.includes("/api/devices/bulk-delete"));
    expect(deletePost).toBeDefined();
    expect(deletePost!.method).toBe("POST");
    expect(await deletePost!.json()).toEqual({ device_ids: ["d1"] });

    // Drawer closes on success.
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
  });

  it("keeps the drawer open when delete fails", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          results: [{ device_id: "d1", ok: false, error: "integration refused" }],
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      ),
    );
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      wrap(
        <EditDeviceDrawer
          opened
          onClose={onClose}
          device={DEVICE}
          areas={AREAS}
        />,
      ),
    );
    await user.click(screen.getByRole("button", { name: "Delete" }));
    const confirmTitle = await screen.findByText(/Delete hue_bulb_3\?/i);
    const modalRoot = confirmTitle.closest('[role="dialog"]') as HTMLElement;
    await user.click(within(modalRoot).getByRole("button", { name: "Delete" }));

    await waitFor(() =>
      expect(screen.queryByText(/Delete hue_bulb_3\?/i)).not.toBeInTheDocument(),
    );
    expect(onClose).not.toHaveBeenCalled();
  });
});
