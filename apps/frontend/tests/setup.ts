import "@testing-library/jest-dom/vitest";

// jsdom doesn't implement matchMedia; Mantine reads it. Stub it.
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
});

// jsdom also lacks ResizeObserver; Mantine Drawer/AppShell use it.
class MockResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
if (!globalThis.ResizeObserver) {
  globalThis.ResizeObserver = MockResizeObserver as unknown as typeof globalThis.ResizeObserver;
}

// jsdom doesn't implement Element.prototype.scrollIntoView; Mantine Combobox
// (used by Select in EditDeviceDrawer) calls it to scroll the active option
// into view after a click. The no-op keeps test output free of unhandled
// errors without affecting any observable behaviour.
Element.prototype.scrollIntoView = () => {};
