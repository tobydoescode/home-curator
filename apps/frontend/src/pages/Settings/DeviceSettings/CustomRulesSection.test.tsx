import { MantineProvider } from "@mantine/core";
import { ModalsProvider } from "@mantine/modals";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CustomRulesSection } from "./CustomRulesSection";
import type { PoliciesFileShape } from "@/hooks/usePolicies";

const draft: PoliciesFileShape = {
  version: 1,
  policies: [
    { id: "nc", type: "naming_convention", enabled: true, severity: "warning", global: { preset: "snake_case" }, starts_with_room: false, rooms: [] } as any,
    {
      id: "aqara-needs-room", type: "custom", scope: "devices",
      enabled: true, severity: "info",
      when: "device.manufacturer == \"Aqara\"", assert: "device.area_id != null",
      message: "Aqara device without a room",
    } as any,
  ],
};

function Harness({ initial }: { initial: PoliciesFileShape }) {
  const [d, setD] = useState(initial);
  return <CustomRulesSection draft={d} onChange={setD} />;
}

function wrap(initial = draft) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <MantineProvider>
      <ModalsProvider>
        <QueryClientProvider client={qc}>
          <MemoryRouter>
            <Harness initial={initial} />
          </MemoryRouter>
        </QueryClientProvider>
      </ModalsProvider>
    </MantineProvider>,
  );
}

describe("CustomRulesSection", () => {
  beforeEach(() => {
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
    vi.stubGlobal("fetch", vi.fn(async () => new Response("{}", { status: 200 })));
  });

  it("lists only custom rules, not naming or built-ins", () => {
    wrap();
    expect(screen.getByText("aqara-needs-room")).toBeInTheDocument();
    expect(screen.queryByText(/^nc$/)).not.toBeInTheDocument();
  });

  it("clicking Add Custom Rule opens the editor", async () => {
    const user = userEvent.setup();
    wrap();
    await user.click(screen.getByRole("button", { name: /add custom rule/i }));
    expect(await screen.findByRole("heading", { name: /edit custom rule|add custom rule/i })).toBeInTheDocument();
  });
});
