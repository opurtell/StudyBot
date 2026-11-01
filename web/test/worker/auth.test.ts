import { env } from "cloudflare:workers";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MAX_LINKS_PER_EMAIL_PER_HOUR, normaliseEmail } from "../../src/worker/auth/routes";
import { sha256Hex } from "../../src/worker/lib/crypto";
import { call, freshIp, lastLinkToken, mockTurnstile, postJson, sessionCookie, signIn, uniqueEmail } from "./helpers";

afterEach(() => vi.restoreAllMocks());

describe("normaliseEmail", () => {
  it("trims and lower-cases", () => {
    expect(normaliseEmail("  Paramedic@Example.COM ")).toBe("paramedic@example.com");
  });
  it.each([undefined, 42, "", "no-at-sign", "a@b", "a b@example.com", `${"x".repeat(250)}@example.com`])(
    "rejects %s",
    (value) => {
      expect(normaliseEmail(value)).toBeNull();
    },
  );
});

describe("magic-link sign-in", () => {
  it("rejects an invalid email before checking Turnstile", async () => {
    const fetchSpy = mockTurnstile(true);
    const res = await postJson("/api/auth/magic-link", { email: "nope", turnstileToken: "ok" });
    expect(res.status).toBe(400);
    expect(await res.json()).toMatchObject({ error: "invalid_email" });
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("refuses to send a link when Turnstile fails", async () => {
    mockTurnstile(false);
    const email = uniqueEmail();
    const res = await postJson("/api/auth/magic-link", { email, turnstileToken: "bad" });
    expect(res.status).toBe(400);
    expect(await res.json()).toMatchObject({ error: "turnstile_failed" });
    const row = await env.DB.prepare("SELECT COUNT(*) AS n FROM login_tokens WHERE email = ?").bind(email).first<{ n: number }>();
    expect(row?.n).toBe(0);
  });

  it("treats an unreachable Turnstile service as a failed check, not a crash", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("network down"));
    const res = await postJson("/api/auth/magic-link", { email: uniqueEmail(), turnstileToken: "ok" });
    expect(res.status).toBe(400);
    expect(await res.json()).toMatchObject({ error: "turnstile_failed" });
  });

  it("stores only a hash of the login token", async () => {
    mockTurnstile(true);
    const email = uniqueEmail();
    await postJson("/api/auth/magic-link", { email, turnstileToken: "ok" });
    const token = lastLinkToken(email);
    const row = await env.DB.prepare("SELECT token_hash FROM login_tokens WHERE email = ?").bind(email).first<{ token_hash: string }>();
    expect(row?.token_hash).toBe(await sha256Hex(token));
    expect(row?.token_hash).not.toContain(token);
  });

  it("signs in with a valid link and shows the free tier quota", async () => {
    const { email, cookie } = await signIn();
    const res = await call("/api/me", { cookie });
    const body = (await res.json()) as { signedIn: boolean; tier: string; email: string; quota: { generations: { limit: number; remaining: number }; marking: { limit: number } } };
    expect(body).toMatchObject({ signedIn: true, tier: "free", email });
    expect(body.quota.generations).toMatchObject({ limit: 20, remaining: 20 });
    expect(body.quota.marking.limit).toBe(30);
  });

  it("sets an HttpOnly, SameSite=Lax, Secure cookie on HTTPS", async () => {
    mockTurnstile(true);
    const email = uniqueEmail();
    await postJson("/api/auth/magic-link", { email, turnstileToken: "ok" });
    const res = await postJson("/api/auth/verify", { token: lastLinkToken(email) });
    const cookie = res.headers.get("set-cookie") ?? "";
    expect(cookie).toMatch(/HttpOnly/i);
    expect(cookie).toMatch(/SameSite=Lax/i);
    expect(cookie).toMatch(/Secure/i);
    expect(sessionCookie(res)).toMatch(/^sb_session=/);
  });

  it("accepts each link only once", async () => {
    mockTurnstile(true);
    const email = uniqueEmail();
    await postJson("/api/auth/magic-link", { email, turnstileToken: "ok" });
    const token = lastLinkToken(email);
    expect((await postJson("/api/auth/verify", { token })).status).toBe(200);
    const again = await postJson("/api/auth/verify", { token });
    expect(again.status).toBe(400);
    expect(await again.json()).toMatchObject({ error: "invalid_or_expired_link" });
  });

  it("rejects an expired link", async () => {
    mockTurnstile(true);
    const email = uniqueEmail();
    await postJson("/api/auth/magic-link", { email, turnstileToken: "ok" });
    const token = lastLinkToken(email);
    await env.DB.prepare("UPDATE login_tokens SET expires_at = ? WHERE email = ?").bind(Date.now() - 1, email).run();
    expect((await postJson("/api/auth/verify", { token })).status).toBe(400);
  });

  it("does not create an account until the link is used", async () => {
    mockTurnstile(true);
    const email = uniqueEmail();
    await postJson("/api/auth/magic-link", { email, turnstileToken: "ok" });
    const row = await env.DB.prepare("SELECT COUNT(*) AS n FROM users WHERE email = ?").bind(email).first<{ n: number }>();
    expect(row?.n).toBe(0);
  });

  it("reuses the same account on a second sign-in", async () => {
    const first = await signIn();
    await signIn(first.email.toUpperCase());
    const row = await env.DB.prepare("SELECT COUNT(*) AS n FROM users WHERE email = ?").bind(first.email).first<{ n: number }>();
    expect(row?.n).toBe(1);
  });

  it("caps links per email per hour without revealing it", async () => {
    mockTurnstile(true);
    const email = uniqueEmail();
    const now = Date.now();
    for (let i = 0; i < MAX_LINKS_PER_EMAIL_PER_HOUR; i += 1) {
      await env.DB.prepare("INSERT INTO login_tokens (token_hash, email, created_at, expires_at) VALUES (?, ?, ?, ?)")
        .bind(`seed-${i}-${email}`, email, now - 1000, now + 60_000)
        .run();
    }
    const res = await postJson("/api/auth/magic-link", { email, turnstileToken: "ok" }, { ip: freshIp() });
    expect(res.status).toBe(202);
    expect(() => lastLinkToken(email)).toThrow();
  });

  it("rate limits repeated requests for one email", async () => {
    mockTurnstile(true);
    const email = uniqueEmail();
    const statuses: number[] = [];
    for (let i = 0; i < 6; i += 1) {
      statuses.push((await postJson("/api/auth/magic-link", { email, turnstileToken: "ok" }, { ip: freshIp() })).status);
    }
    expect(statuses).toContain(429);
  });

  it("signs out and invalidates the session server-side", async () => {
    const { cookie } = await signIn();
    const out = await postJson("/api/auth/sign-out", {}, { cookie });
    expect(out.status).toBe(200);
    const me = await call("/api/me", { cookie });
    expect(await me.json()).toEqual({ signedIn: false, tier: "anonymous" });
  });

  it("rejects an expired session", async () => {
    const { cookie } = await signIn();
    await env.DB.prepare("UPDATE sessions SET expires_at = ?").bind(Date.now() - 1).run();
    const me = await call("/api/me", { cookie });
    expect(await me.json()).toEqual({ signedIn: false, tier: "anonymous" });
  });
});

describe("account deletion", () => {
  it("requires a session", async () => {
    const res = await call("/api/me", { method: "DELETE", headers: { origin: "https://studybot.test" } });
    expect(res.status).toBe(401);
  });

  it("removes the user, sessions and login tokens", async () => {
    const { email, cookie } = await signIn();
    const res = await call("/api/me", { method: "DELETE", headers: { origin: "https://studybot.test" }, cookie });
    expect(res.status).toBe(200);
    const counts = await env.DB.prepare(
      "SELECT (SELECT COUNT(*) FROM users WHERE email = ?1) AS users, (SELECT COUNT(*) FROM login_tokens WHERE email = ?1) AS tokens",
    )
      .bind(email)
      .first<{ users: number; tokens: number }>();
    expect(counts).toEqual({ users: 0, tokens: 0 });
    expect(await (await call("/api/me", { cookie })).json()).toEqual({ signedIn: false, tier: "anonymous" });
  });
});
