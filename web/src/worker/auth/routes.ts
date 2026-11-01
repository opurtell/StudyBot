import { Hono, type Context } from "hono";
import { deleteCookie, getCookie, setCookie } from "hono/cookie";
import { apiError, clientIp } from "../lib/http";
import { summariseQuota } from "../lib/quota";
import type { AppEnv } from "../types";
import { buildAuthorisationUrl, exchangeCode, GoogleAuthError } from "./google";
import { createSession, destroySession, secureCookies, upsertGoogleUser } from "./sessions";

export const OAUTH_COOKIE = "sb_oauth";
const OAUTH_TTL_SECONDS = 10 * 60;

function redirectUri(c: Context<AppEnv>): string {
  return `${new URL(c.req.url).origin}/api/auth/google/callback`;
}

function signInFailed(c: Context<AppEnv>, reason: string) {
  return c.redirect(`/sign-in?error=${encodeURIComponent(reason)}`, 302);
}

export const authRoutes = new Hono<AppEnv>();

authRoutes.get("/google/start", async (c) => {
  const { success } = await c.env.RL_SIGNIN_IP.limit({ key: `ip:${clientIp(c)}` });
  if (!success) return signInFailed(c, "rate_limited");
  if (!c.env.GOOGLE_CLIENT_ID) {
    c.get("log").error("google_oauth_not_configured");
    return signInFailed(c, "unavailable");
  }
  const start = await buildAuthorisationUrl(c.env.GOOGLE_CLIENT_ID, redirectUri(c));
  setCookie(c, OAUTH_COOKIE, JSON.stringify({ s: start.state, v: start.codeVerifier, n: start.nonce }), {
    path: "/api/auth/google",
    httpOnly: true,
    secure: secureCookies(c),
    sameSite: "Lax",
    maxAge: OAUTH_TTL_SECONDS,
  });
  return c.redirect(start.url, 302);
});

authRoutes.get("/google/callback", async (c) => {
  const log = c.get("log");
  const raw = getCookie(c, OAUTH_COOKIE);
  deleteCookie(c, OAUTH_COOKIE, { path: "/api/auth/google", secure: secureCookies(c), httpOnly: true, sameSite: "Lax" });

  if (c.req.query("error")) {
    log.info("google_sign_in_cancelled", { googleError: c.req.query("error") });
    return signInFailed(c, "cancelled");
  }
  let pending: { s: string; v: string; n: string } | null = null;
  try {
    pending = raw ? JSON.parse(raw) : null;
  } catch {
    pending = null;
  }
  const code = c.req.query("code");
  const state = c.req.query("state");
  if (!pending || !code || !state || state !== pending.s) {
    log.warn("google_state_mismatch");
    return signInFailed(c, "expired");
  }

  try {
    const identity = await exchangeCode({
      clientId: c.env.GOOGLE_CLIENT_ID,
      clientSecret: c.env.GOOGLE_CLIENT_SECRET,
      code,
      codeVerifier: pending.v,
      redirectUri: redirectUri(c),
      nonce: pending.n,
    });
    const now = Date.now();
    const user = await upsertGoogleUser(c.env.DB, identity, now);
    await destroySession(c, c.get("sessionHash"));
    await createSession(c, user.id, now);
    log.info("signed_in", { userId: user.id, method: "google" });
    return c.redirect("/", 302);
  } catch (err) {
    if (err instanceof GoogleAuthError) {
      log.warn("google_sign_in_rejected", { reason: err.reason });
      return signInFailed(c, err.reason === "email_not_verified" ? "unverified_email" : "failed");
    }
    throw err;
  }
});

authRoutes.post("/dev-sign-in", async (c) => {
  const host = new URL(c.req.url).hostname;
  if (c.env.ENVIRONMENT !== "development" || (host !== "localhost" && host !== "127.0.0.1")) {
    return apiError(c, 404, "not_found", "No such endpoint.");
  }
  const now = Date.now();
  const user = await upsertGoogleUser(c.env.DB, { sub: "dev-user", email: "dev@localhost" }, now);
  await destroySession(c, c.get("sessionHash"));
  await createSession(c, user.id, now);
  return c.json({ ok: true });
});

authRoutes.post("/sign-out", async (c) => {
  await destroySession(c, c.get("sessionHash"));
  return c.json({ ok: true });
});

export const meRoutes = new Hono<AppEnv>();

meRoutes.get("/", (c) => {
  const user = c.get("user");
  if (!user) return c.json({ signedIn: false, tier: "anonymous" as const });
  return c.json({
    signedIn: true,
    tier: user.plan,
    email: user.email,
    quota: summariseQuota(c.env, user),
  });
});

meRoutes.delete("/", async (c) => {
  const user = c.get("user");
  if (!user) return apiError(c, 401, "unauthorised", "Sign in first.");
  await c.env.DB.batch([
    c.env.DB.prepare(`DELETE FROM sessions WHERE user_id = ?1`).bind(user.id),
    c.env.DB.prepare(`DELETE FROM users WHERE id = ?1`).bind(user.id),
  ]);
  await destroySession(c, null);
  c.get("log").info("account_deleted", { userId: user.id });
  return c.json({ ok: true });
});
