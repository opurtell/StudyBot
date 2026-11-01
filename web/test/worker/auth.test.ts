import { env } from "cloudflare:workers";
import { afterEach, describe, expect, it, vi } from "vitest";
import { validateIdTokenClaims } from "../../src/worker/auth/google";
import { sha256Base64Url } from "../../src/worker/lib/crypto";
import { call, completeGoogle, cookieFrom, mockGoogleToken, signIn, startGoogle, TEST_CLIENT_ID, validClaims } from "./helpers";

afterEach(() => vi.restoreAllMocks());

const errorOf = (res: Response) => new URL(res.headers.get("location") ?? "", "https://x").searchParams.get("error");

describe("Google sign-in start", () => {
  it("redirects to Google with PKCE, state and nonce", async () => {
    const { res, location, oauthCookie } = await startGoogle();
    expect(res.status).toBe(302);
    expect(location.origin + location.pathname).toBe("https://accounts.google.com/o/oauth2/v2/auth");
    expect(location.searchParams.get("client_id")).toBe(TEST_CLIENT_ID);
    expect(location.searchParams.get("redirect_uri")).toBe("https://studybot.test/api/auth/google/callback");
    expect(location.searchParams.get("scope")).toBe("openid email");
    expect(location.searchParams.get("code_challenge_method")).toBe("S256");
    expect(location.searchParams.get("state")).toMatch(/^[A-Za-z0-9_-]{40,}$/);
    expect(location.searchParams.get("nonce")).toMatch(/^[A-Za-z0-9_-]{40,}$/);
    expect(oauthCookie).toBeTruthy();
  });

  it("keeps the PKCE verifier server-side in an HttpOnly cookie scoped to the callback", async () => {
    const { res, location } = await startGoogle();
    const raw = res.headers.getSetCookie().find((c) => c.startsWith("sb_oauth=")) ?? "";
    expect(raw).toMatch(/HttpOnly/i);
    expect(raw).toMatch(/Path=\/api\/auth\/google/);
    expect(raw).toMatch(/SameSite=Lax/i);
    const stored = JSON.parse(decodeURIComponent(raw.split(";")[0].slice("sb_oauth=".length)));
    expect(await sha256Base64Url(stored.v)).toBe(location.searchParams.get("code_challenge"));
    expect(location.search).not.toContain(stored.v);
  });

  it("rate limits repeated starts from one IP", async () => {
    const statuses: (string | null)[] = [];
    for (let i = 0; i < 12; i += 1) statuses.push(errorOf((await startGoogle("198.51.100.9")).res));
    expect(statuses).toContain("rate_limited");
  });
});

describe("Google sign-in callback", () => {
  it("creates an account and session from a valid ID token", async () => {
    const { res, session } = await completeGoogle((nonce) => validClaims(nonce, { sub: "sub-create" , email: "Create@Example.com" }));
    expect(res.status).toBe(302);
    expect(res.headers.get("location")).toBe("/");
    expect(session).toBeTruthy();
    const me = (await (await call("/api/me", { cookie: session! })).json()) as Record<string, unknown>;
    expect(me).toMatchObject({ signedIn: true, tier: "free", email: "create@example.com" });
  });

  it("sends the code, verifier and secret to Google's token endpoint", async () => {
    const started = await startGoogle();
    const spy = mockGoogleToken(() => validClaims(started.nonce, { sub: "sub-body" }));
    await call(`/api/auth/google/callback?code=abc&state=${started.state}`, { cookie: started.oauthCookie ?? "" });
    const body = new URLSearchParams(String(spy.mock.calls[0][1]?.body));
    expect(body.get("code")).toBe("abc");
    expect(body.get("grant_type")).toBe("authorization_code");
    expect(body.get("client_secret")).toBe("test-google-secret");
    expect(await sha256Base64Url(body.get("code_verifier") ?? "")).toBe(started.location.searchParams.get("code_challenge"));
  });

  it("clears the one-time OAuth cookie", async () => {
    const { res } = await completeGoogle((nonce) => validClaims(nonce, { sub: "sub-clear" }));
    const cleared = res.headers.getSetCookie().find((c) => c.startsWith("sb_oauth="));
    expect(cleared).toMatch(/Max-Age=0/i);
  });

  it("rejects a state that doesn't match the cookie", async () => {
    const started = await startGoogle();
    const spy = mockGoogleToken(() => ({}));
    const res = await call(`/api/auth/google/callback?code=abc&state=forged`, { cookie: started.oauthCookie ?? "" });
    expect(errorOf(res)).toBe("expired");
    expect(spy).not.toHaveBeenCalled();
    expect(cookieFrom(res, "sb_session")).toBeNull();
  });

  it("rejects a callback with no OAuth cookie", async () => {
    const started = await startGoogle();
    const res = await call(`/api/auth/google/callback?code=abc&state=${started.state}`);
    expect(errorOf(res)).toBe("expired");
  });

  it("reports a cancelled sign-in", async () => {
    const started = await startGoogle();
    const res = await call(`/api/auth/google/callback?error=access_denied&state=${started.state}`, { cookie: started.oauthCookie ?? "" });
    expect(errorOf(res)).toBe("cancelled");
  });

  it.each([
    ["wrong audience", { aud: "someone-else" }, "failed"],
    ["wrong issuer", { iss: "https://evil.example" }, "failed"],
    ["expired token", { exp: Math.floor(Date.now() / 1000) - 3600 }, "failed"],
    ["unverified email", { email_verified: false }, "unverified_email"],
    ["missing email", { email: undefined }, "failed"],
  ])("rejects an ID token with %s", async (_label, overrides, expected) => {
    const { res, session } = await completeGoogle((nonce) => validClaims(nonce, { sub: `sub-${crypto.randomUUID()}`, ...overrides }));
    expect(errorOf(res)).toBe(expected);
    expect(session).toBeNull();
  });

  it("rejects an ID token minted for a different sign-in attempt", async () => {
    const { res, session } = await completeGoogle(() => validClaims("some-other-nonce"));
    expect(errorOf(res)).toBe("failed");
    expect(session).toBeNull();
  });

  it("fails cleanly when Google's token endpoint errors", async () => {
    const started = await startGoogle();
    mockGoogleToken(() => ({}), 500);
    const res = await call(`/api/auth/google/callback?code=abc&state=${started.state}`, { cookie: started.oauthCookie ?? "" });
    expect(errorOf(res)).toBe("failed");
  });

  it("reuses the account for the same Google user and follows email changes", async () => {
    await signIn("sub-stable", "old@example.com");
    const { cookie } = await signIn("sub-stable", "new@example.com");
    const rows = await env.DB.prepare("SELECT email FROM users WHERE google_sub = 'sub-stable'").all<{ email: string }>();
    expect(rows.results).toEqual([{ email: "new@example.com" }]);
    expect(await (await call("/api/me", { cookie })).json()).toMatchObject({ email: "new@example.com" });
  });

  it("shows the free tier quota once signed in", async () => {
    const { cookie } = await signIn();
    const body = (await (await call("/api/me", { cookie })).json()) as { quota: { generations: { limit: number; remaining: number }; marking: { limit: number } } };
    expect(body.quota.generations).toMatchObject({ limit: 20, remaining: 20 });
    expect(body.quota.marking.limit).toBe(30);
  });

  it("sets an HttpOnly, SameSite=Lax, Secure session cookie on HTTPS", async () => {
    const { res } = await completeGoogle((nonce) => validClaims(nonce, { sub: "sub-cookie" }));
    const raw = res.headers.getSetCookie().find((c) => c.startsWith("sb_session=")) ?? "";
    expect(raw).toMatch(/HttpOnly/i);
    expect(raw).toMatch(/SameSite=Lax/i);
    expect(raw).toMatch(/Secure/i);
  });
});

describe("validateIdTokenClaims", () => {
  const expected = { clientId: TEST_CLIENT_ID, nonce: "n", nowSeconds: 1_000_000 };
  const base = { iss: "accounts.google.com", aud: TEST_CLIENT_ID, sub: "s", email: " A@B.com ", email_verified: "true", exp: 1_000_100, nonce: "n" };

  it("accepts Google's string form of email_verified and normalises the email", () => {
    expect(validateIdTokenClaims(base, expected)).toEqual({ sub: "s", email: "a@b.com" });
  });

  it("accepts an audience list that includes the client", () => {
    expect(validateIdTokenClaims({ ...base, aud: ["other", TEST_CLIENT_ID] }, expected).sub).toBe("s");
  });
});

describe("sessions", () => {
  it("signs out and invalidates the session server-side", async () => {
    const { cookie } = await signIn();
    const out = await call("/api/auth/sign-out", {
      method: "POST",
      headers: { origin: "https://studybot.test", "content-type": "application/json" },
      body: "{}",
      cookie,
    });
    expect(out.status).toBe(200);
    expect(await (await call("/api/me", { cookie })).json()).toEqual({ signedIn: false, tier: "anonymous" });
  });

  it("rejects an expired session", async () => {
    const { cookie } = await signIn();
    await env.DB.prepare("UPDATE sessions SET expires_at = ?").bind(Date.now() - 1).run();
    expect(await (await call("/api/me", { cookie })).json()).toEqual({ signedIn: false, tier: "anonymous" });
  });
});

describe("dev sign-in", () => {
  it("is hidden off localhost even in development", async () => {
    const res = await call("/api/auth/dev-sign-in", {
      method: "POST",
      headers: { origin: "https://studybot.test", "content-type": "application/json" },
      body: "{}",
    });
    expect(res.status).toBe(404);
  });

  it("is not advertised off localhost", async () => {
    expect(await (await call("/api/config")).json()).toMatchObject({ devSignIn: false });
  });
});

describe("account deletion", () => {
  it("requires a session", async () => {
    const res = await call("/api/me", { method: "DELETE", headers: { origin: "https://studybot.test" } });
    expect(res.status).toBe(401);
  });

  it("removes the user and their sessions", async () => {
    const { cookie } = await signIn("sub-delete", "delete@example.com");
    const res = await call("/api/me", { method: "DELETE", headers: { origin: "https://studybot.test" }, cookie });
    expect(res.status).toBe(200);
    const row = await env.DB.prepare("SELECT COUNT(*) AS n FROM users WHERE google_sub = 'sub-delete'").first<{ n: number }>();
    expect(row?.n).toBe(0);
    expect(await (await call("/api/me", { cookie })).json()).toEqual({ signedIn: false, tier: "anonymous" });
  });
});
