import { MantineProvider } from "@mantine/core";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CustomRuleEditor } from "./CustomRuleEditor";

function wrap(props: { initial?: any | null; onSaved?: (r: any) => void; onClose?: () => void } = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <MantineProvider>
      <QueryClientProvider client={qc}>
        <CustomRuleEditor
          initial={props.initial ?? null}
          onSaved={props.onSaved ?? vi.fn()}
          onClose={props.onClose ?? vi.fn()}
        />
      </QueryClientProvider>
    </MantineProvider>,
  );
}

describe("CustomRuleEditor", () => {
  beforeEach(() => {
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
    vi.stubGlobal("fetch", vi.fn(async (req: Request) => {
      const url = typeof req === "string" ? req : req.url;
      if (url.includes("/api/policies/compile")) {
        return new Response(JSON.stringify({ ok: true }), { status: 200 });
      }
      return new Response("{}", { status: 200 });
    }));
  });

  it("renders multiline textareas for when / assert / message", () => {
    wrap();
    const when = screen.getByRole("textbox", { name: /^when$/i }) as HTMLTextAreaElement;
    const asrt = screen.getByRole("textbox", { name: /^assert$/i }) as HTMLTextAreaElement;
    const msg = screen.getByRole("textbox", { name: /^message$/i }) as HTMLTextAreaElement;
    expect(when.tagName).toBe("TEXTAREA");
    expect(asrt.tagName).toBe("TEXTAREA");
    expect(msg.tagName).toBe("TEXTAREA");
  });

  it("calls onSaved with the built rule on Save", async () => {
    const user = userEvent.setup();
    const onSaved = vi.fn();
    wrap({ onSaved });
    await user.type(screen.getByRole("textbox", { name: /^name$/i }), "My Rule");
    await user.clear(screen.getByRole("textbox", { name: /^assert$/i }));
    await user.type(screen.getByRole("textbox", { name: /^assert$/i }), "true");
    await user.clear(screen.getByRole("textbox", { name: /^message$/i }));
    await user.type(screen.getByRole("textbox", { name: /^message$/i }), "msg");
    await user.click(screen.getByRole("button", { name: /save/i }));
    expect(onSaved).toHaveBeenCalled();
    const saved = onSaved.mock.calls[0][0];
    expect(saved.type).toBe("custom");
    expect(saved.scope).toBe("devices");
    expect(saved.assert).toBe("true");
  });
});
