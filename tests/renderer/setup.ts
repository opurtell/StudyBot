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

// Node 26 defines its own non-configurable `localStorage` global, which stops
// vitest's jsdom environment from attaching jsdom's implementation. Provide a
// spec-shaped in-memory Storage when that happens.
if (typeof window.localStorage === "undefined") {
  const store = new Map<string, string>();
  const memoryStorage: Storage = {
    get length() {
      return store.size;
    },
    key: (index: number) => Array.from(store.keys())[index] ?? null,
    getItem: (key: string) => (store.has(key) ? store.get(key)! : null),
    setItem: (key: string, value: string) => {
      store.set(String(key), String(value));
    },
    removeItem: (key: string) => {
      store.delete(String(key));
    },
    clear: () => {
      store.clear();
    },
  };
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    writable: true,
    value: memoryStorage,
  });
}

beforeEach(() => {
  window.localStorage.clear();
});
