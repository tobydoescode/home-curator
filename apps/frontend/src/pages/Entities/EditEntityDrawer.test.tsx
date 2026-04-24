import "@testing-library/jest-dom/vitest";

import { MantineProvider } from "@mantine/core";
import { ModalsProvider } from "@mantine/modals";
import { Notifications } from "@mantine/notifications";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { EditEntityDrawer, type EditEntityDrawerEntity } from "./EditEntityDrawer";

const ENTITY: EditEntityDrawerEntity = {
  entity_id: "light.office_lamp",
  name: null,
  original_name: "Office Lamp",
  domain: "light",
  platform: "hue",
  device_id: "d1",
  device_name: "Office Hue",
  area_id: "office",
  area_name: "Office",
  disabled_by: null,
  hidden_by: null,
  icon: null,
  issues: [],
};

const AREAS = [
  { id: "office", name: "Office" },
  { id: "study", name: "Study" },
];

beforeEach(() => {
  window.HTMLElement.prototype.scrollIntoView = vi.fn();
});
afterEach(() => vi.restoreAllMocks());

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <MantineProvider>
      <Notifications />
      <ModalsProvider>
        <QueryClientProvider client={qc}>
          <MemoryRouter initialEntries={["/entities"]}>
            <Routes>
              <Route path="/entities" element={ui} />
              <Route path="/devices" element={<div>devices page</div>} />
            </Routes>
          </MemoryRouter>
        </QueryClientProvider>
      </ModalsProvider>
    </MantineProvider>
  );
}

describe("EditEntityDrawer", () => {
  it("seeds Entity ID and Name from the prop and shows the always-visible warning", () => {
    render(
      wrap(<EditEntityDrawer opened onClose={() => {}} entity={ENTITY} areas={AREAS} />),
    );
    // The Entity ID input holds only the object_id portion; the domain is
    // shown as a readonly leftSection.
    expect((screen.getByLabelText("Entity ID") as HTMLInputElement).value).toBe(
      "office_lamp",
    );
    expect(
      screen.getByText(/Renaming the entity ID can break references/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/Spook/)).toBeInTheDocument();
  });

  it("re-seeds form state when the entity prop swaps to a different entity_id", () => {
    const { rerender } = render(
      wrap(<EditEntityDrawer opened onClose={() => {}} entity={ENTITY} areas={AREAS} />),
    );
    rerender(
      wrap(
        <EditEntityDrawer
          opened
          onClose={() => {}}
          entity={{ ...ENTITY, entity_id: "light.other" }}
          areas={AREAS}
        />,
      ),
    );
    expect((screen.getByLabelText("Entity ID") as HTMLInputElement).value).toBe(
      "other",
    );
  });

  it("invalid slug → red border + Save disabled", async () => {
    const user = userEvent.setup();
    render(
      wrap(<EditEntityDrawer opened onClose={() => {}} entity={ENTITY} areas={AREAS} />),
    );
    const slugInput = screen.getByLabelText("Entity ID");
    await user.clear(slugInput);
    // Uppercase not allowed in object_id (snake_case only).
    await user.type(slugInput, "Bad_Case");
    expect(slugInput).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
  });

  it("Name-only dirty saves directly without the rename confirm", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    );
    const user = userEvent.setup();
    render(
      wrap(<EditEntityDrawer opened onClose={() => {}} entity={ENTITY} areas={AREAS} />),
    );
    await user.type(screen.getByLabelText("Name"), "Office Lamp 2");
    await user.click(screen.getByRole("button", { name: "Save" }));
    // Never shows the rename-confirm title
    expect(screen.queryByText(/Rename Entity ID\?/i)).not.toBeInTheDocument();
    await waitFor(() => expect(fetchSpy).toHaveBeenCalled());
    const req = fetchSpy.mock.calls.find((c) =>
      (c[0] as Request).url.includes("/api/entities/"),
    )![0] as Request;
    expect(await req.json()).toEqual({ name: "Office Lamp 2" });
  });

  it("entity_id dirty → RenameConfirmModal gate, then PATCH on confirm", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    );
    const user = userEvent.setup();
    render(
      wrap(<EditEntityDrawer opened onClose={() => {}} entity={ENTITY} areas={AREAS} />),
    );
    const slugInput = screen.getByLabelText("Entity ID");
    await user.clear(slugInput);
    // Domain "light." is rendered as a non-editable leftSection; user
    // types only the new object_id.
    await user.type(slugInput, "study_lamp");
    await user.click(screen.getByRole("button", { name: "Save" }));

    const title = await screen.findByText(/Rename Entity ID\?/i);
    const modalRoot = title.closest('[role="dialog"]') as HTMLElement;
    await user.click(within(modalRoot).getByRole("button", { name: "Rename" }));

    await waitFor(() => expect(fetchSpy).toHaveBeenCalled());
    const req = fetchSpy.mock.calls.find((c) =>
      (c[0] as Request).url.includes("/api/entities/light.office_lamp"),
    )![0] as Request;
    expect(await req.json()).toEqual({ new_entity_id: "light.study_lamp" });
  });

  it("Keep on the rename confirm does NOT send any PATCH", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    );
    const user = userEvent.setup();
    render(
      wrap(<EditEntityDrawer opened onClose={() => {}} entity={ENTITY} areas={AREAS} />),
    );
    const slugInput = screen.getByLabelText("Entity ID");
    await user.clear(slugInput);
    // Domain "light." is rendered as a non-editable leftSection; user
    // types only the new object_id.
    await user.type(slugInput, "study_lamp");
    await user.click(screen.getByRole("button", { name: "Save" }));
    const title = await screen.findByText(/Rename Entity ID\?/i);
    const modalRoot = title.closest('[role="dialog"]') as HTMLElement;
    await user.click(within(modalRoot).getByRole("button", { name: "Keep" }));

    const patches = fetchSpy.mock.calls
      .map((c) => c[0] as Request)
      .filter((r) => r.method === "PATCH");
    expect(patches).toHaveLength(0);
  });

  it("Enabled toggle flips → payload sets disabled_by: 'user'", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    );
    const user = userEvent.setup();
    render(
      wrap(<EditEntityDrawer opened onClose={() => {}} entity={ENTITY} areas={AREAS} />),
    );
    await user.click(screen.getByRole("switch", { name: /Enabled/i }));
    await user.click(screen.getByRole("button", { name: "Save" }));
    const req = fetchSpy.mock.calls.find((c) =>
      (c[0] as Request).url.includes("/api/entities/"),
    )![0] as Request;
    expect(await req.json()).toEqual({ disabled_by: "user" });
  });

  it("Visible toggle flips → payload sets hidden_by: 'user'", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    );
    const user = userEvent.setup();
    render(
      wrap(<EditEntityDrawer opened onClose={() => {}} entity={ENTITY} areas={AREAS} />),
    );
    await user.click(screen.getByRole("switch", { name: /Visible/i }));
    await user.click(screen.getByRole("button", { name: "Save" }));
    const req = fetchSpy.mock.calls.find((c) =>
      (c[0] as Request).url.includes("/api/entities/"),
    )![0] as Request;
    expect(await req.json()).toEqual({ hidden_by: "user" });
  });

  it("Device link click navigates to /devices?device=<device_id>", async () => {
    const user = userEvent.setup();
    render(
      wrap(<EditEntityDrawer opened onClose={() => {}} entity={ENTITY} areas={AREAS} />),
    );
    await user.click(screen.getByRole("button", { name: /Office Hue/i }));
    expect(await screen.findByText("devices page")).toBeInTheDocument();
  });

  it("dirty close-guard prompts discard confirm", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      wrap(<EditEntityDrawer opened onClose={onClose} entity={ENTITY} areas={AREAS} />),
    );
    await user.type(screen.getByLabelText("Name"), "x");
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(await screen.findByText(/Discard changes\?/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Keep editing/i }));
    expect(onClose).not.toHaveBeenCalled();
  });

  it("Delete skips the dirty-guard and fires delete-entity after confirm", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ results: [{ entity_id: "light.office_lamp", ok: true }] }),
        { status: 200 },
      ),
    );
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      wrap(<EditEntityDrawer opened onClose={onClose} entity={ENTITY} areas={AREAS} />),
    );
    // Dirty the form first; Delete must still skip the discard guard.
    await user.type(screen.getByLabelText("Name"), "x");
    await user.click(screen.getByRole("button", { name: "Delete" }));
    const confirmTitle = await screen.findByText(/Delete Office Lamp\?/i);
    const modalRoot = confirmTitle.closest('[role="dialog"]') as HTMLElement;
    await user.click(within(modalRoot).getByRole("button", { name: "Delete" }));

    const deletePost = fetchSpy.mock.calls
      .map((c) => c[0] as Request)
      .find((r) => r.url.includes("/api/entities/bulk-delete"));
    expect(deletePost).toBeDefined();
    expect(await deletePost!.json()).toEqual({ entity_ids: ["light.office_lamp"] });
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
  });
});
