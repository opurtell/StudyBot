import { render } from "@testing-library/react";
import axe from "axe-core";
import { MemoryRouter } from "react-router";
import { vi } from "vitest";
import { App } from "../../src/client/App";

type Handler = (init: RequestInit | undefined) => { status?: number; body: unknown };

export function mockApi(routes: Record<string, Handler | unknown>) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.pathname : input.url;
    const method = (init?.method ?? "GET").toUpperCase();
    const key = `${method} ${url}`;
    const route = routes[key] ?? routes[key.split("?")[0]!] ?? (key.startsWith("GET /api/topics?") ? { view: "icp_pacer", topics: [] } : undefined);
    if (route === undefined) throw new Error(`Unmocked API call: ${key}`);
    const result =
      typeof route === "function"
        ? (route as Handler)(init)
        : route && typeof route === "object" && "status" in route && "body" in route
          ? (route as { status: number; body: unknown })
          : { body: route };
    return new Response(JSON.stringify(result.body), {
      status: result.status ?? 200,
      headers: { "content-type": "application/json" },
    });
  });
}

export const anonymous = { signedIn: false, tier: "anonymous" };
export const signedIn = {
  signedIn: true,
  tier: "free",
  email: "medic@example.com",
  quota: {
    period: "2026-11",
    generations: { used: 3, limit: 20, remaining: 17 },
    marking: { used: 0, limit: 30, remaining: 30 },
  },
};

export function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

export async function axeViolations(container: Element) {
  const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
  return results.violations.map((v) => `${v.id}: ${v.help} (${v.nodes.length})`);
}
