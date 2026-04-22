import { MantineProvider } from "@mantine/core";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { BuiltInRulesSection } from "./BuiltInRulesSection";
import type { PoliciesFileShape } from "@/hooks/usePolicies";

const initialDraft: PoliciesFileShape = {
  version: 1,
  policies: [
    { id: "mr", type: "missing_area", enabled: true, severity: "warning" } as any,
    { id: "re", type: "reappeared_after_delete", enabled: false, severity: "info" } as any,
  ],
};

function Harness({ initial, spy }: { initial: PoliciesFileShape; spy: (d: PoliciesFileShape) => void }) {
  const [draft, setDraft] = useState(initial);
  return (
    <BuiltInRulesSection
      draft={draft}
      onChange={(d) => { spy(d); setDraft(d); }}
    />
  );
}

function wrap(initial = initialDraft) {
  const spy = vi.fn();
  const utils = render(
    <MantineProvider>
      <Harness initial={initial} spy={spy} />
    </MantineProvider>,
  );
  return { spy, ...utils };
}

describe("BuiltInRulesSection", () => {
  it("renders one card per built-in rule with its explanation", () => {
    wrap();
    expect(screen.getByRole("heading", { name: "Missing Room" })).toBeInTheDocument();
    expect(screen.getByText(/no assigned area/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Reappeared After Delete" })).toBeInTheDocument();
  });

  it("toggling enabled emits a patched draft", async () => {
    const user = userEvent.setup();
    const { spy } = wrap();
    await user.click(screen.getByRole("switch", { name: /enable missing room/i }));
    const next = spy.mock.calls.at(-1)![0];
    const mr = next.policies.find((p: any) => p.id === "mr");
    expect(mr.enabled).toBe(false);
  });
});
