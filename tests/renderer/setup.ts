import "@testing-library/jest-dom";
import { beforeEach } from "vitest";

// jsdom does not implement window.matchMedia — provide a minimal mock
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


Object.defineProperty(window, "api", {
  writable: true,
  value: {
    backend: {
      getStatus: () => Promise.resolve({ state: "ready", message: null }),
      waitForReady: () => Promise.resolve({ state: "ready", message: null }),
      restart: () => Promise.resolve({ state: "ready", message: null }),
      onStatusChange: () => () => {},
    },
  },
});

beforeEach(() => {
  window.localStorage.clear();
});
