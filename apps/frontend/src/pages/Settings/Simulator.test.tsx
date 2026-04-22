import { MantineProvider } from "@mantine/core";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { Simulator } from "./Simulator";

describe("Simulator", () => {
  it("shows counts + groups; Failing expanded by default, Passing collapsed", async () => {
    const user = userEvent.setup();
    render(
      <MantineProvider>
        <Simulator result={{
          ok: true, error: null,
          counts: { matched_when: 3, passes_assert: 1, fails_assert: 1, errored: 1 },
          failing: [{ id: "d1", name: "Bad", room: "LR", message: "fail" }],
          errored: [{ id: "d2", name: "Err", room: null, error: "boom" }],
          passing: [{ id: "d3", name: "Good", room: "LR" }],
        } as any} />
      </MantineProvider>,
    );
    expect(screen.getByText(/matched when.*3/i)).toBeInTheDocument();
    expect(screen.getByText("Bad")).toBeInTheDocument();
    expect(screen.getByText("Err")).toBeInTheDocument();
    expect(screen.queryByText("Good")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /passing/i }));
    expect(screen.getByText("Good")).toBeInTheDocument();
  });

  it("shows parse error in place of results", () => {
    render(
      <MantineProvider>
        <Simulator result={{ ok: false, error: "bad cel", counts: null, failing: [], errored: [], passing: [] } as any} />
      </MantineProvider>,
    );
    expect(screen.getByText(/bad cel/)).toBeInTheDocument();
    expect(screen.queryByText(/matched when/i)).not.toBeInTheDocument();
  });
});
