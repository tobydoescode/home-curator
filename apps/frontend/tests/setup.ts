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
