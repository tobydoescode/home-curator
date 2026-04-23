import { MantineProvider } from "@mantine/core";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { afterEach, describe, expect, it } from "vitest";

import { ColorSchemeToggle } from "./ColorSchemeToggle";

function wrap(ui: React.ReactElement, defaultColorScheme: "light" | "dark" | "auto" = "auto") {
  return render(<MantineProvider defaultColorScheme={defaultColorScheme}>{ui}</MantineProvider>);
}

afterEach(() => {
  localStorage.clear();
});

describe("ColorSchemeToggle", () => {
  it("renders an accessible button with a Color Scheme label", () => {
    wrap(<ColorSchemeToggle />);
    expect(
      screen.getByRole("button", { name: /color scheme/i }),
    ).toBeInTheDocument();
  });

  it("opens a menu with Light, Dark, and System options when clicked", async () => {
    const user = userEvent.setup();
    wrap(<ColorSchemeToggle />);
    await user.click(screen.getByRole("button", { name: /color scheme/i }));
    expect(await screen.findByRole("menuitem", { name: /light/i })).toBeInTheDocument();
    expect(await screen.findByRole("menuitem", { name: /dark/i })).toBeInTheDocument();
    expect(await screen.findByRole("menuitem", { name: /system/i })).toBeInTheDocument();
  });

  it("sets data-mantine-color-scheme to dark when Dark is selected", async () => {
    const user = userEvent.setup();
    wrap(<ColorSchemeToggle />, "light");
    await user.click(screen.getByRole("button", { name: /color scheme/i }));
    await user.click(await screen.findByRole("menuitem", { name: /dark/i }));
    expect(document.documentElement.getAttribute("data-mantine-color-scheme")).toBe("dark");
  });

  it("sets data-mantine-color-scheme to light when Light is selected", async () => {
    const user = userEvent.setup();
    wrap(<ColorSchemeToggle />, "dark");
    await user.click(screen.getByRole("button", { name: /color scheme/i }));
    await user.click(await screen.findByRole("menuitem", { name: /light/i }));
    expect(document.documentElement.getAttribute("data-mantine-color-scheme")).toBe("light");
  });
});
