import { Hono } from "hono";
import { apiError, clientIp } from "../lib/http";
import { randomToken, sha256Hex } from "../lib/crypto";
import { summariseQuota } from "../lib/quota";
import type { AppEnv } from "../types";
import { buildMagicLinkEmail, sendEmail } from "./email";
import { createSession, destroySession, upsertUserByEmail } from "./sessions";
import { verifyTurnstile } from "./turnstile";

export const LOGIN_TOKEN_TTL_MINUTES = 15;
export const MAX_LINKS_PER_EMAIL_PER_HOUR = 5;
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function normaliseEmail(raw: unknown): string | null {
  if (typeof raw !== "string") return null;
  const email = raw.trim().toLowerCase();
  if (email.length < 3 || email.length > 254 || !EMAIL_PATTERN.test(email)) return null;
  return email;
}

async function readJson(req: Request): Promise<Record<string, unknown> | null> {
  try {
    const body = await req.json();
    return body && typeof body === "object" && !Array.isArray(body) ? (body as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

export const authRoutes = new Hono<AppEnv>();

authRoutes.post("/magic-link", async (c) => {
  const log = c.get("log");
  const body = await readJson(c.req.raw);
  if (!body) return apiError(c, 400, "bad_request", "Send a JSON body.");
  const email = normaliseEmail(body.email);
  if (!email) return apiError(c, 400, "invalid_email", "Enter a valid email address.");

  const ip = clientIp(c);
  const [ipLimit, emailLimit] = await Promise.all([
    c.env.RL_SIGNIN_IP.limit({ key: `ip:${ip}` }),
    c.env.RL_SIGNIN_EMAIL.limit({ key: `email:${await sha256Hex(email)}` }),
  ]);
  if (!ipLimit.success || !emailLimit.success) {
    log.warn("signin_rate_limited", { byIp: !ipLimit.success, byEmail: !emailLimit.success });
    return apiError(c, 429, "rate_limited", "Too many sign-in requests. Wait a minute and try again.");
  }

  const turnstileToken = typeof body.turnstileToken === "string" ? body.turnstileToken : "";
  const turnstile = await verifyTurnstile(c.env.TURNSTILE_SECRET_KEY, turnstileToken, ip, c.get("requestId"));
  if (!turnstile.success) {
    log.warn("turnstile_failed", { codes: turnstile.errorCodes.join(",") });
    return apiError(c, 400, "turnstile_failed", "The human check failed. Reload the page and try again.");
  }

  const now = Date.now();
  const recent = await c.env.DB.prepare(
    `SELECT COUNT(*) AS n FROM login_tokens WHERE email = ?1 AND created_at > ?2`,
  )
    .bind(email, now - 60 * 60 * 1000)
    .first<{ n: number }>();
  if ((recent?.n ?? 0) >= MAX_LINKS_PER_EMAIL_PER_HOUR) {
    log.warn("signin_hourly_cap_reached");
    return c.json({ ok: true }, 202);
  }

  const token = randomToken();
  await c.env.DB.prepare(
    `INSERT INTO login_tokens (token_hash, email, created_at, expires_at) VALUES (?1, ?2, ?3, ?4)`,
  )
    .bind(await sha256Hex(token), email, now, now + LOGIN_TOKEN_TTL_MINUTES * 60 * 1000)
    .run();

  const origin = new URL(c.req.url).origin;
  const link = `${origin}/auth/verify#token=${token}`;
  await sendEmail(c.env, log, buildMagicLinkEmail(email, link, LOGIN_TOKEN_TTL_MINUTES));
  log.info("magic_link_sent");
  return c.json({ ok: true }, 202);
});

authRoutes.post("/verify", async (c) => {
  const body = await readJson(c.req.raw);
  const token = typeof body?.token === "string" ? body.token : "";
  if (!token || token.length > 128) {
    return apiError(c, 400, "invalid_or_expired_link", "This sign-in link is invalid or has expired.");
  }
  const now = Date.now();
  const claimed = await c.env.DB.prepare(
    `UPDATE login_tokens SET used_at = ?2
      WHERE token_hash = ?1 AND used_at IS NULL AND expires_at > ?2
      RETURNING email`,
  )
    .bind(await sha256Hex(token), now)
    .first<{ email: string }>();
  if (!claimed) {
    c.get("log").info("magic_link_rejected");
    return apiError(c, 400, "invalid_or_expired_link", "This sign-in link is invalid or has expired.");
  }
  const user = await upsertUserByEmail(c.env.DB, claimed.email, now);
  await destroySession(c, c.get("sessionHash"));
  await createSession(c, user.id, now);
  c.get("log").info("signed_in", { userId: user.id });
  return c.json({ ok: true, user: { email: user.email, plan: user.plan } });
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
    c.env.DB.prepare(`DELETE FROM login_tokens WHERE email = ?1`).bind(user.email),
    c.env.DB.prepare(`DELETE FROM users WHERE id = ?1`).bind(user.id),
  ]);
  await destroySession(c, null);
  c.get("log").info("account_deleted", { userId: user.id });
  return c.json({ ok: true });
});
