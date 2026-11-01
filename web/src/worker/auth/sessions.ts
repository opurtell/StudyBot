import type { Context } from "hono";
import { deleteCookie, getCookie, setCookie } from "hono/cookie";
import { randomToken, sha256Hex } from "../lib/crypto";
import { currentQuotaPeriod } from "../lib/quota";
import type { AppEnv, SessionUser } from "../types";

export const SESSION_COOKIE = "sb_session";
export const SESSION_TTL_MS = 30 * 24 * 60 * 60 * 1000;
const TOUCH_INTERVAL_MS = 60 * 60 * 1000;

interface UserRow {
  id: string;
  email: string;
  plan: "free";
  is_admin: number;
  quota_period: string;
  free_gen_used: number;
  free_eval_used: number;
}

function toSessionUser(row: UserRow): SessionUser {
  return {
    id: row.id,
    email: row.email,
    plan: row.plan,
    isAdmin: row.is_admin === 1,
    quotaPeriod: row.quota_period,
    freeGenUsed: row.free_gen_used,
    freeEvalUsed: row.free_eval_used,
  };
}

export function secureCookies(c: Context<AppEnv>): boolean {
  return new URL(c.req.url).protocol === "https:";
}

export async function upsertGoogleUser(
  db: D1Database,
  identity: { sub: string; email: string },
  now: number,
): Promise<SessionUser> {
  const row = await db
    .prepare(
      `INSERT INTO users (id, email, google_sub, quota_period, created_at, last_sign_in_at)
       VALUES (?1, ?2, ?3, ?4, ?5, ?5)
       ON CONFLICT (google_sub) DO UPDATE SET email = excluded.email, last_sign_in_at = excluded.last_sign_in_at
       RETURNING id, email, plan, is_admin, quota_period, free_gen_used, free_eval_used`,
    )
    .bind(crypto.randomUUID(), identity.email, identity.sub, currentQuotaPeriod(new Date(now)), now)
    .first<UserRow>();
  if (!row) throw new Error("user upsert returned no row");
  return toSessionUser(row);
}

export async function createSession(c: Context<AppEnv>, userId: string, now: number): Promise<void> {
  const token = randomToken();
  const idHash = await sha256Hex(token);
  await c.env.DB.prepare(
    `INSERT INTO sessions (id_hash, user_id, created_at, expires_at, last_seen_at) VALUES (?1, ?2, ?3, ?4, ?3)`,
  )
    .bind(idHash, userId, now, now + SESSION_TTL_MS)
    .run();
  setCookie(c, SESSION_COOKIE, token, {
    path: "/",
    httpOnly: true,
    secure: secureCookies(c),
    sameSite: "Lax",
    maxAge: Math.floor(SESSION_TTL_MS / 1000),
  });
}

export async function loadSession(c: Context<AppEnv>): Promise<{ user: SessionUser; idHash: string } | null> {
  const token = getCookie(c, SESSION_COOKIE);
  if (!token || token.length > 128) return null;
  const idHash = await sha256Hex(token);
  const now = Date.now();
  const row = await c.env.DB.prepare(
    `SELECT u.id, u.email, u.plan, u.is_admin, u.quota_period, u.free_gen_used, u.free_eval_used,
            s.expires_at AS session_expires_at, s.last_seen_at AS session_last_seen_at
       FROM sessions s JOIN users u ON u.id = s.user_id
      WHERE s.id_hash = ?1`,
  )
    .bind(idHash)
    .first<UserRow & { session_expires_at: number; session_last_seen_at: number }>();
  if (!row) return null;
  if (row.session_expires_at <= now) {
    await c.env.DB.prepare(`DELETE FROM sessions WHERE id_hash = ?1`).bind(idHash).run();
    return null;
  }
  if (now - row.session_last_seen_at > TOUCH_INTERVAL_MS) {
    await c.env.DB.prepare(`UPDATE sessions SET last_seen_at = ?2, expires_at = ?3 WHERE id_hash = ?1`)
      .bind(idHash, now, now + SESSION_TTL_MS)
      .run();
  }
  return { user: toSessionUser(row), idHash };
}

export async function destroySession(c: Context<AppEnv>, idHash: string | null): Promise<void> {
  if (idHash) await c.env.DB.prepare(`DELETE FROM sessions WHERE id_hash = ?1`).bind(idHash).run();
  deleteCookie(c, SESSION_COOKIE, { path: "/", secure: secureCookies(c), httpOnly: true, sameSite: "Lax" });
}

export async function purgeExpired(db: D1Database, now: number): Promise<{ sessions: number }> {
  const result = await db.prepare(`DELETE FROM sessions WHERE expires_at <= ?1`).bind(now).run();
  return { sessions: result.meta.changes ?? 0 };
}
