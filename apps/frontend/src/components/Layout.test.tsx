import { MantineProvider } from "@mantine/core";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { Layout } from "./Layout";

const STORAGE_KEY = "home-curator:sidebar-desktop-opened";

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <MantineProvider>
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={["/devices"]}>
          <Routes>
            <Route path="/" element={<Layout />}>
              <Route path="devices" element={<div>Devices Page</div>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    </MantineProvider>,
  );
}

afterEach(() => {
  localStorage.clear();
});

describe("Layout", () => {
  it("renders the sidebar nav links expanded by default", () => {
    wrap();
    expect(screen.getByText("Devices")).toBeInTheDocument();
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });

  it("exposes burger toggles with accessible labels", () => {
    wrap();
    expect(screen.getByLabelText("Toggle Sidebar")).toBeInTheDocument();
    expect(screen.getByLabelText("Toggle Navigation")).toBeInTheDocument();
  });

  it("persists the collapsed state when the desktop burger is clicked", async () => {
    const user = userEvent.setup();
    wrap();
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
    await user.click(screen.getByLabelText("Toggle Sidebar"));
    expect(localStorage.getItem(STORAGE_KEY)).toBe("false");
    await user.click(screen.getByLabelText("Toggle Sidebar"));
    expect(localStorage.getItem(STORAGE_KEY)).toBe("true");
  });

  it("restores the collapsed state from localStorage on mount", () => {
    localStorage.setItem(STORAGE_KEY, "false");
    wrap();
    const desktopBurger = screen.getByLabelText("Toggle Sidebar");
    expect(desktopBurger.querySelector("[data-opened]")).toBeNull();
  });

  it("renders the desktop burger as opened when state is true", () => {
    localStorage.setItem(STORAGE_KEY, "true");
    wrap();
    const desktopBurger = screen.getByLabelText("Toggle Sidebar");
    expect(desktopBurger.querySelector("[data-opened]")).not.toBeNull();
  });

  it("renders the color scheme toggle in the header", () => {
    wrap();
    expect(
      screen.getByRole("button", { name: /color scheme/i }),
    ).toBeInTheDocument();
  });
});
