import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

// jsdom implements neither of these, and framer-motion / the invite dialog both
// reach for them.
if (!window.matchMedia) {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })) as unknown as typeof window.matchMedia;
}

if (!window.crypto?.randomUUID) {
  Object.defineProperty(window, "crypto", {
    value: { ...window.crypto, randomUUID: () => "00000000-0000-4000-8000-000000000000" },
  });
}

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
window.ResizeObserver ??= ResizeObserverStub as never;

// jsdom has no layout engine, so scrollTo is a no-op rather than a warning.
window.scrollTo = (() => {}) as typeof window.scrollTo;
Element.prototype.scrollIntoView = () => {};
