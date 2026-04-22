import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import App from "./App";

describe("App", () => {
  it("renders the sidebar title", () => {
    render(<App />);
    expect(screen.getByText("Home Curator")).toBeInTheDocument();
  });
});
