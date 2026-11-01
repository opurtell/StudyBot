import { env } from "cloudflare:workers";
import { vi } from "vitest";
import { app } from "../../src/worker/app";

export const ORIGIN = "https://studybot.test";
let ipCounter = 0;

export function freshIp(): string {
  ipCounter += 1;
  return `203.0.113.${ipCounter % 250}`;
}

export function call(path: string, init: RequestInit & { ip?: string; cookie?: string } = {}) {
  const headers = new Headers(init.headers);
  headers.set("cf-connecting-ip", init.ip ?? freshIp());
  if (init.cookie) headers.set("cookie", init.cookie);
  return app.request(`${ORIGIN}${path}`, { ...init, headers }, env);
}

export function postJson(path: string, body: unknown, opts: { ip?: string; cookie?: string; origin?: string | null } = {}) {
  const headers: Record<string, string> = { "content-type": "application/json" };
  if (opts.origin !== null) headers.origin = opts.origin ?? ORIGIN;
  return call(path, { method: "POST", headers, body: JSON.stringify(body), ip: opts.ip, cookie: opts.cookie });
}

export const TEST_CLIENT_ID = "test-client.apps.googleusercontent.com";

function b64url(value: string): string {
  return btoa(value).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export function fakeIdToken(claims: Record<string, unknown>): string {
  return `${b64url(JSON.stringify({ alg: "RS256", typ: "JWT" }))}.${b64url(JSON.stringify(claims))}.sig`;
}

export function mockGoogleToken(claimsFor: (nonce: string) => Record<string, unknown>, status = 200) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    if (url === "https://oauth2.googleapis.com/token") {
      if (status !== 200) return new Response("nope", { status });
      const body = new URLSearchParams(String(init?.body));
      const nonce = pendingNonces.get(body.get("code") ?? "") ?? "";
      return Response.json({ id_token: fakeIdToken(claimsFor(nonce)) });
    }
    throw new Error(`Unexpected outbound fetch in test: ${url}`);
  });
}

const pendingNonces = new Map<string, string>();

export function cookieFrom(res: Response, name: string): string | null {
  for (const part of res.headers.getSetCookie()) {
    const match = part.match(new RegExp(`^${name}=([^;]*)`));
    if (match && match[1]) return `${name}=${match[1]}`;
  }
  return null;
}

export async function startGoogle(ip?: string) {
  const res = await call("/api/auth/google/start", { ip });
  const location = new URL(res.headers.get("location") ?? "", ORIGIN);
  const oauthCookie = cookieFrom(res, "sb_oauth");
  return { res, location, oauthCookie, state: location.searchParams.get("state") ?? "", nonce: location.searchParams.get("nonce") ?? "" };
}

export function validClaims(nonce: string, overrides: Record<string, unknown> = {}) {
  return {
    iss: "https://accounts.google.com",
    aud: TEST_CLIENT_ID,
    sub: "google-sub-1",
    email: "Medic@Example.com",
    email_verified: true,
    exp: Math.floor(Date.now() / 1000) + 3600,
    nonce,
    ...overrides,
  };
}

export async function completeGoogle(claims: (nonce: string) => Record<string, unknown>, opts: { code?: string } = {}) {
  const started = await startGoogle();
  const code = opts.code ?? `code-${crypto.randomUUID()}`;
  pendingNonces.set(code, started.nonce);
  mockGoogleToken(claims);
  const res = await call(`/api/auth/google/callback?code=${code}&state=${started.state}`, { cookie: started.oauthCookie ?? "" });
  return { res, session: cookieFrom(res, "sb_session") };
}

export async function signIn(sub = `sub-${crypto.randomUUID()}`, email = `${sub}@example.com`) {
  const { res, session } = await completeGoogle((nonce) => validClaims(nonce, { sub, email }));
  if (!session) throw new Error(`Google callback did not sign in: ${res.headers.get("location")}`);
  return { email, cookie: session };
}
