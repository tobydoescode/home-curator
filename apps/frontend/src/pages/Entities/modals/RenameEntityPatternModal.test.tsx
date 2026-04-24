import "@testing-library/jest-dom/vitest";

import { MantineProvider } from "@mantine/core";
import { Notifications } from "@mantine/notifications";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { RenameEntityPatternModal } from "./RenameEntityPatternModal";

const ENTITY_IDS = ["light.office_lamp", "light.office_strip"];

beforeEach(() => {
  window.HTMLElement.prototype.scrollIntoView = vi.fn();
});
afterEach(() => vi.restoreAllMocks());

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <MantineProvider>
      <Notifications />
      <QueryClientProvider client={qc}>{ui}</QueryClientProvider>
    </MantineProvider>
  );
}

describe("RenameEntityPatternModal", () => {
  it("renders two independently-checkable sections (Entity ID + Friendly Name)", () => {
    render(
      wrap(
        <RenameEntityPatternModal entityIds={ENTITY_IDS} onClose={() => {}} />,
      ),
    );
    expect(screen.getByRole("checkbox", { name: /Entity ID/i })).toBeChecked();
    expect(
      screen.getByRole("checkbox", { name: /Friendly Name/i }),
    ).toBeChecked();
  });

  it("invalid id-regex disables Apply on that side only; friendly-name side still usable", async () => {
    const user = userEvent.setup();
    render(
      wrap(
        <RenameEntityPatternModal entityIds={ENTITY_IDS} onClose={() => {}} />,
      ),
    );
    const idPattern = screen.getByLabelText(
      /^Pattern.*Entity ID/i,
    ) as HTMLInputElement;
    // user.type() treats '[' as a key modifier; escape it with '[[' so the
    // character lands in the field literally.
    await user.type(idPattern, "[[unclosed");
    act(() => {
      idPattern.blur();
    });
    await waitFor(() =>
      expect(screen.getByText(/Invalid regex/i)).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: /Apply/i })).toBeDisabled();
    await user.click(screen.getByRole("checkbox", { name: /Entity ID/i }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /Apply/i })).not.toBeDisabled(),
    );
  });

  it("Dry Run fetches with dry_run: true and populates preview without writing", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          results: [
            {
              entity_id: "light.office_lamp",
              id_changed: true,
              new_entity_id: "light.study_lamp",
              name_changed: true,
              new_name: "Study Lamp",
              ok: true,
              dry_run: true,
            },
          ],
          error: null,
        }),
        { status: 200 },
      ),
    );
    const user = userEvent.setup();
    render(
      wrap(
        <RenameEntityPatternModal entityIds={ENTITY_IDS} onClose={() => {}} />,
      ),
    );
    await user.type(
      screen.getByLabelText(/^Pattern.*Entity ID/i),
      "^light\\.office_(.+)$",
    );
    await user.type(
      screen.getByLabelText(/^Replacement.*Entity ID/i),
      "light.study_$1",
    );
    await user.click(screen.getByRole("button", { name: /Dry Run/i }));
    const req = fetchSpy.mock.calls[0][0] as Request;
    expect(await req.json()).toMatchObject({ dry_run: true });
    expect(await screen.findByText(/light\.office_lamp/)).toBeInTheDocument();
    expect(screen.getByText(/light\.study_lamp/)).toBeInTheDocument();
  });

  it("Apply fires with dry_run: false and sends both field groups", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          results: [{ entity_id: "light.office_lamp", ok: true }],
          error: null,
        }),
        { status: 200 },
      ),
    );
    const user = userEvent.setup();
    render(
      wrap(
        <RenameEntityPatternModal entityIds={ENTITY_IDS} onClose={() => {}} />,
      ),
    );
    await user.type(
      screen.getByLabelText(/^Pattern.*Entity ID/i),
      "^light\\.(.+)$",
    );
    await user.type(
      screen.getByLabelText(/^Replacement.*Entity ID/i),
      "light.x_$1",
    );
    await user.type(
      screen.getByLabelText(/^Pattern.*Friendly Name/i),
      "^(.+)$",
    );
    await user.type(
      screen.getByLabelText(/^Replacement.*Friendly Name/i),
      "X $1",
    );
    await user.click(screen.getByRole("button", { name: /^Apply$/i }));
    const req = fetchSpy.mock.calls[0][0] as Request;
    expect(await req.json()).toMatchObject({
      dry_run: false,
      id_pattern: "^light\\.(.+)$",
      id_replacement: "light.x_$1",
      name_pattern: "^(.+)$",
      name_replacement: "X $1",
    });
  });

  it("caps preview at 100 rows with '… (N more)' overflow", async () => {
    const rows = Array.from({ length: 120 }, (_, i) => ({
      entity_id: `light.x${i}`,
      id_changed: true,
      new_entity_id: `light.y${i}`,
      name_changed: false,
      ok: true,
      dry_run: true,
    }));
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ results: rows, error: null }), {
        status: 200,
      }),
    );
    const user = userEvent.setup();
    render(
      wrap(
        <RenameEntityPatternModal
          entityIds={rows.map((r) => r.entity_id)}
          onClose={() => {}}
        />,
      ),
    );
    await user.type(
      screen.getByLabelText(/^Pattern.*Entity ID/i),
      "^light\\.x(.+)$",
    );
    await user.type(
      screen.getByLabelText(/^Replacement.*Entity ID/i),
      "light.y$1",
    );
    await user.click(screen.getByRole("button", { name: /Dry Run/i }));
    expect(await screen.findByText(/… \(20 more\)/)).toBeInTheDocument();
  });
});
