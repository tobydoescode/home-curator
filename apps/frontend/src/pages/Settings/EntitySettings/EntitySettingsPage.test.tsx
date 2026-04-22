import { MantineProvider } from "@mantine/core";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EntitySettingsPage } from "./EntitySettingsPage";

describe("EntitySettingsPage", () => {
  it("renders placeholder copy", () => {
    render(
      <MantineProvider>
        <EntitySettingsPage />
      </MantineProvider>,
    );
    expect(screen.getByRole("heading", { name: "Entity Settings" })).toBeInTheDocument();
    expect(screen.getByText(/not yet available|coming soon|ship with the entities view/i)).toBeInTheDocument();
  });
});
