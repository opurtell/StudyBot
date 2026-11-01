import { afterEach, describe, expect, it, vi } from "vitest";
import { call, postJson } from "./helpers";

afterEach(() => vi.restoreAllMocks());

describe("API basics", () => {
  it("reports health without caching", async () => {
    const res = await call("/api/health");
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ ok: true, environment: "development" });
    expect(res.headers.get("cache-control")).toBe("no-store");
    expect(res.headers.get("x-request-id")).toBeTruthy();
  });

  it("exposes only public config", async () => {
    const res = await call("/api/config");
    const body = (await res.json()) as Record<string, unknown>;
    expect(Object.keys(body).sort()).toEqual(["devSignIn", "environment"]);
  });

  it("returns a JSON 404 for unknown API paths", async () => {
    const res = await call("/api/nope");
    expect(res.status).toBe(404);
    expect(await res.json()).toMatchObject({ error: "not_found" });
  });

  it("treats a request without a session as anonymous", async () => {
    const res = await call("/api/me");
    expect(await res.json()).toEqual({ signedIn: false, tier: "anonymous" });
  });

  it("ignores a forged session cookie", async () => {
    const res = await call("/api/me", { cookie: "sb_session=not-a-real-session" });
    expect(await res.json()).toEqual({ signedIn: false, tier: "anonymous" });
  });

  it("rejects state-changing requests from another origin", async () => {
    const res = await postJson("/api/auth/sign-out", {}, { origin: "https://evil.example" });
    expect(res.status).toBe(403);
  });

  it("rejects state-changing requests with no Origin header", async () => {
    const res = await postJson("/api/auth/sign-out", {}, { origin: null });
    expect(res.status).toBe(403);
  });

  it("rejects non-JSON bodies", async () => {
    const res = await call("/api/auth/sign-out", {
      method: "POST",
      headers: { origin: "https://studybot.test", "content-type": "application/x-www-form-urlencoded" },
      body: "x=1",
    });
    expect(res.status).toBe(415);
  });

  it("rate limits a single IP across the API", async () => {
    const ip = "198.51.100.77";
    const statuses: number[] = [];
    for (let i = 0; i < 125; i += 1) statuses.push((await call("/api/health", { ip })).status);
    expect(statuses.filter((s) => s === 429).length).toBeGreaterThan(0);
  });
});
