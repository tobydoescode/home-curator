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
