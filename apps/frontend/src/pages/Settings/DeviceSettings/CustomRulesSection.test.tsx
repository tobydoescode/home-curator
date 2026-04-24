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

function Harness({
  initial,
  scope = "devices",
}: {
  initial: PoliciesFileShape;
  scope?: "devices" | "entities";
}) {
  const [d, setD] = useState(initial);
  return <CustomRulesSection draft={d} onChange={setD} scope={scope} />;
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

describe("CustomRulesSection — scope prop", () => {
  const mixed: PoliciesFileShape = {
    version: 1,
    policies: [
      {
        id: "nc",
        type: "naming_convention",
        enabled: true,
        severity: "warning",
        global: { preset: "snake_case" },
        starts_with_room: false,
        rooms: [],
      } as any,
      {
        id: "dev-rule",
        type: "custom",
        scope: "devices",
        enabled: true,
        severity: "info",
        when: "true",
        assert: "device.name != null",
        message: "msg1",
      } as any,
      {
        id: "ent-rule",
        type: "custom",
        scope: "entities",
        enabled: true,
        severity: "info",
        when: "true",
        assert: "entity.name != null",
        message: "msg2",
      } as any,
    ],
  };

  beforeEach(() => {
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("{}", { status: 200 })),
    );
  });

  it("scope=devices filters out entity-scoped custom rules", () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <MantineProvider>
        <ModalsProvider>
          <QueryClientProvider client={qc}>
            <MemoryRouter>
              <Harness initial={mixed} scope="devices" />
            </MemoryRouter>
          </QueryClientProvider>
        </ModalsProvider>
      </MantineProvider>,
    );
    expect(screen.getByText("dev-rule")).toBeInTheDocument();
    expect(screen.queryByText("ent-rule")).not.toBeInTheDocument();
  });

  it("scope=entities filters out device-scoped custom rules", () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <MantineProvider>
        <ModalsProvider>
          <QueryClientProvider client={qc}>
            <MemoryRouter>
              <Harness initial={mixed} scope="entities" />
            </MemoryRouter>
          </QueryClientProvider>
        </ModalsProvider>
      </MantineProvider>,
    );
    expect(screen.getByText("ent-rule")).toBeInTheDocument();
    expect(screen.queryByText("dev-rule")).not.toBeInTheDocument();
  });
});
