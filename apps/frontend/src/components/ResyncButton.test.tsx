import { MantineProvider } from "@mantine/core";
import { Notifications } from "@mantine/notifications";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ResyncButton } from "./ResyncButton";

afterEach(() => {
  vi.restoreAllMocks();
});

function wrap(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return (
    <MantineProvider>
      <Notifications />
      <QueryClientProvider client={client}>{ui}</QueryClientProvider>
    </MantineProvider>
  );
}

describe("ResyncButton", () => {
  it("renders an accessible button with a resync tooltip label", () => {
    render(wrap(<ResyncButton />));
    expect(
      screen.getByRole("button", { name: /resync with home assistant/i }),
    ).toBeInTheDocument();
  });

  it("POSTs to /api/cache/resync when clicked", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ added: 0, removed: 0, updated: 0 }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    const user = userEvent.setup();
    render(wrap(<ResyncButton />));
    await user.click(
      screen.getByRole("button", { name: /resync with home assistant/i }),
    );

    await waitFor(() => {
      const req = fetchSpy.mock.calls[0]?.[0] as Request | undefined;
      expect(req?.url).toContain("/api/cache/resync");
      expect(req?.method).toBe("POST");
    });
  });

  it("disables the button while the request is in flight", async () => {
    let resolveFetch: ((r: Response) => void) | null = null;
    vi.spyOn(globalThis, "fetch").mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveFetch = resolve;
        }),
    );
    const user = userEvent.setup();
    render(wrap(<ResyncButton />));
    const button = screen.getByRole("button", {
      name: /resync with home assistant/i,
    });
    await user.click(button);

    await waitFor(() => expect(button).toBeDisabled());

    resolveFetch!(
      new Response(JSON.stringify({ added: 0, removed: 0, updated: 0 }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    await waitFor(() => expect(button).not.toBeDisabled());
  });
});
