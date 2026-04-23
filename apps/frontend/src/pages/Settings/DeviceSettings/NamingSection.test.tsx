import { MantineProvider } from "@mantine/core";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useState } from "react";

import { NamingSection } from "./NamingSection";
import type { PoliciesFileShape } from "@/hooks/usePolicies";

const draft: PoliciesFileShape = {
  version: 1,
  policies: [{
    id: "nc", type: "naming_convention", enabled: true, severity: "warning",
    global: { preset: "snake_case" }, starts_with_room: false, rooms: [],
  }],
};

function StatefulWrapper({ initial = draft, spy = vi.fn() }: { initial?: PoliciesFileShape; spy?: ReturnType<typeof vi.fn> }) {
  const [d, setD] = useState(initial);
  const onChange = (next: PoliciesFileShape) => { setD(next); spy(next); };
  const qc = new QueryClient();
  return (
    <MantineProvider>
      <QueryClientProvider client={qc}>
        <NamingSection draft={d} onChange={onChange} />
      </QueryClientProvider>
    </MantineProvider>
  );
}

function wrap(initial = draft, spy = vi.fn()) {
  const result = render(<StatefulWrapper initial={initial} spy={spy} />);
  return { onChange: spy, ...result };
}

describe("NamingSection — global", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("[]", { status: 200 })));
    // jsdom doesn't implement scrollIntoView; stub it to suppress Mantine Combobox noise
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
  });

  it("shows the preset label in the dropdown", () => {
    wrap();
    // Mantine Select renders multiple inputs (visible + hidden); at least one has the value.
    const inputs = screen.getAllByDisplayValue(/snake_case/);
    expect(inputs.length).toBeGreaterThan(0);
  });

  it("makes Pattern editable only when preset is Custom Regex", async () => {
    const user = userEvent.setup();
    wrap();
    expect(screen.queryByLabelText(/pattern/i)).not.toBeInTheDocument();
    // Mantine Select: getAllByLabelText returns visible + hidden input; click the first
    const presetInputs = screen.getAllByLabelText(/preset/i);
    await user.click(presetInputs[0]);
    await user.click(await screen.findByText("Custom Regex"));
    expect(screen.getByLabelText(/pattern/i)).toBeInTheDocument();
  });

  it("emits draft with starts_with_room=true when toggle clicked", async () => {
    const user = userEvent.setup();
    const { onChange } = wrap();
    await user.click(screen.getByRole("switch", { name: /starts with room name/i }));
    expect(onChange).toHaveBeenCalled();
    const next: PoliciesFileShape = onChange.mock.calls.at(-1)![0];
    const nc = next.policies.find((p) => p.type === "naming_convention")!;
    expect((nc as any).starts_with_room).toBe(true);
  });
});

describe("NamingSection — overrides", () => {
  beforeEach(() => {
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
    vi.stubGlobal("fetch", vi.fn(async (req: Request) => {
      const url = typeof req === "string" ? req : req.url;
      if (url.includes("/api/areas")) {
        return new Response(JSON.stringify([
          { id: "lr", name: "Living Room" },
          { id: "mgmt", name: "Management" },
        ]), { status: 200 });
      }
      return new Response("[]", { status: 200 });
    }));
  });

  it("adds an override with a real-area room picker", async () => {
    const user = userEvent.setup();
    const { onChange } = wrap();
    await user.click(await screen.findByRole("button", { name: /add override/i }));
    // The new row's Room select — pick Management by name.
    const rooms = screen.getAllByLabelText(/^Room 0$/);
    await user.click(rooms[0]);
    await user.click(await screen.findByText("Management"));
    const last = onChange.mock.calls.at(-1)![0];
    const nc = last.policies.find((p: any) => p.type === "naming_convention");
    expect(nc.rooms[0].area_id).toBe("mgmt");
    expect(nc.rooms[0].enabled).toBe(true);
    expect(nc.rooms[0].preset).toBeTruthy();
  });

  it("selecting Disabled preset flips enabled=false and hides pattern/starts-with", async () => {
    const user = userEvent.setup();
    const initial = structuredClone(draft);
    (initial.policies[0] as any).rooms = [{ area_id: "mgmt", enabled: true, preset: "snake_case" }];
    const { onChange } = wrap(initial);
    const presetSelects = screen.getAllByLabelText(/Preset for room 0/i);
    await user.click(presetSelects[0]);
    await user.click(await screen.findByText("Disabled"));
    const last = onChange.mock.calls.at(-1)![0];
    const override = (last.policies[0] as any).rooms[0];
    expect(override.enabled).toBe(false);
    expect(override.preset).toBeNull();
  });
});

describe("NamingBlockSection (generic)", () => {
  beforeEach(() => {
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify([{ id: "lr", name: "Living Room" }]),
            { status: 200 },
          ),
      ),
    );
  });

  it("renders the block editor without preset dropdown when showPreset=false", async () => {
    const { NamingBlockSection } = await import("./NamingSection");
    const qc = new QueryClient();
    render(
      <MantineProvider>
        <QueryClientProvider client={qc}>
          <NamingBlockSection
            block={{ preset: "snake_case", starts_with_room: false, rooms: [] }}
            onBlockChange={() => {}}
            showPreset={false}
            allowCustomPattern={false}
          />
        </QueryClientProvider>
      </MantineProvider>,
    );
    expect(screen.queryByLabelText(/preset/i)).not.toBeInTheDocument();
    expect(
      screen.getByRole("switch", { name: /starts with room/i }),
    ).toBeInTheDocument();
  });

  it("emits onBlockChange when starts_with_room flips", async () => {
    const { NamingBlockSection } = await import("./NamingSection");
    const spy = vi.fn();
    const qc = new QueryClient();
    const user = userEvent.setup();
    render(
      <MantineProvider>
        <QueryClientProvider client={qc}>
          <NamingBlockSection
            block={{ preset: "snake_case", starts_with_room: false, rooms: [] }}
            onBlockChange={spy}
          />
        </QueryClientProvider>
      </MantineProvider>,
    );
    await user.click(screen.getByRole("switch", { name: /starts with room/i }));
    expect(spy).toHaveBeenCalledWith(
      expect.objectContaining({ starts_with_room: true }),
    );
  });
});
