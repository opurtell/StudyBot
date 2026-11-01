import { env } from "cloudflare:workers";
import { vi } from "vitest";
import { app } from "../../src/worker/app";
import { devOutbox } from "../../src/worker/auth/email";

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

export function mockTurnstile(success = true) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    if (url.startsWith("https://challenges.cloudflare.com/")) {
      return Response.json({ success, "error-codes": success ? [] : ["invalid-input-response"] });
    }
    throw new Error(`Unexpected outbound fetch in test: ${url}`);
  });
}

export function lastLinkToken(to: string): string {
  const message = [...devOutbox].reverse().find((m) => m.to === to.toLowerCase());
  if (!message) throw new Error(`No email captured for ${to}`);
  const match = message.text.match(/#token=([A-Za-z0-9_-]+)/);
  if (!match) throw new Error("No token in email");
  return match[1];
}

export function sessionCookie(res: Response): string {
  const raw = res.headers.get("set-cookie") ?? "";
  const match = raw.match(/sb_session=([^;]+)/);
  if (!match) throw new Error("No session cookie set");
  return `sb_session=${match[1]}`;
}

let emailCounter = 0;
export function uniqueEmail(): string {
  emailCounter += 1;
  return `paramedic${emailCounter}-${crypto.randomUUID().slice(0, 8)}@example.com`;
}

export async function signIn(email = uniqueEmail()): Promise<{ email: string; cookie: string }> {
  mockTurnstile(true);
  const req = await postJson("/api/auth/magic-link", { email, turnstileToken: "ok" });
  if (req.status !== 202) throw new Error(`magic-link returned ${req.status}`);
  const res = await postJson("/api/auth/verify", { token: lastLinkToken(email) });
  if (res.status !== 200) throw new Error(`verify returned ${res.status}`);
  return { email, cookie: sessionCookie(res) };
}
