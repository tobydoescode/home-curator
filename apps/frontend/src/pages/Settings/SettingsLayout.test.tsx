import { MantineProvider } from "@mantine/core";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, it, expect } from "vitest";

import { SettingsLayout } from "./SettingsLayout";

function wrap(path: string) {
  return render(
    <MantineProvider>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/settings" element={<SettingsLayout />}>
            <Route path="devices" element={<div>Device Settings Content</div>} />
            <Route path="entities" element={<div>Entity Settings Content</div>} />
            <Route path="global" element={<div>Global Policies Content</div>} />
            <Route path="exceptions" element={<div>Exceptions Content</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </MantineProvider>,
  );
}

describe("SettingsLayout", () => {
  it("renders sub-nav and active child route", () => {
    wrap("/settings/devices");
    expect(screen.getByRole("link", { name: "Device Settings" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Entity Settings" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Global Policies" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Exceptions" })).toBeInTheDocument();
    expect(screen.getByText("Device Settings Content")).toBeInTheDocument();
  });
});
