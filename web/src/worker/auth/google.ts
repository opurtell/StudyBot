import { randomToken, sha256Base64Url } from "../lib/crypto";

export const GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth";
export const GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token";
const GOOGLE_ISSUERS = new Set(["https://accounts.google.com", "accounts.google.com"]);

export interface OAuthStart {
  url: string;
  state: string;
  codeVerifier: string;
  nonce: string;
}

export interface GoogleIdentity {
  sub: string;
  email: string;
}

export class GoogleAuthError extends Error {
  constructor(readonly reason: string) {
    super(`Google sign-in failed: ${reason}`);
    this.name = "GoogleAuthError";
  }
}

export async function buildAuthorisationUrl(clientId: string, redirectUri: string): Promise<OAuthStart> {
  const state = randomToken();
  const codeVerifier = randomToken(48);
  const nonce = randomToken();
  const params = new URLSearchParams({
    client_id: clientId,
    redirect_uri: redirectUri,
    response_type: "code",
    scope: "openid email",
    state,
    nonce,
    code_challenge: await sha256Base64Url(codeVerifier),
    code_challenge_method: "S256",
    prompt: "select_account",
  });
  return { url: `${GOOGLE_AUTH_URL}?${params}`, state, codeVerifier, nonce };
}

function decodeJwtPayload(jwt: string): Record<string, unknown> {
  const parts = jwt.split(".");
  if (parts.length !== 3) throw new GoogleAuthError("malformed_id_token");
  try {
    const base64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const json = new TextDecoder().decode(Uint8Array.from(atob(base64), (ch) => ch.charCodeAt(0)));
    const payload = JSON.parse(json);
    if (!payload || typeof payload !== "object") throw new Error("not an object");
    return payload as Record<string, unknown>;
  } catch {
    throw new GoogleAuthError("malformed_id_token");
  }
}

export function validateIdTokenClaims(
  claims: Record<string, unknown>,
  expected: { clientId: string; nonce: string; nowSeconds: number },
): GoogleIdentity {
  if (typeof claims.iss !== "string" || !GOOGLE_ISSUERS.has(claims.iss)) throw new GoogleAuthError("bad_issuer");
  const aud = claims.aud;
  const audOk = aud === expected.clientId || (Array.isArray(aud) && aud.includes(expected.clientId));
  if (!audOk) throw new GoogleAuthError("bad_audience");
  if (typeof claims.exp !== "number" || claims.exp <= expected.nowSeconds - 60) throw new GoogleAuthError("expired");
  if (claims.nonce !== expected.nonce) throw new GoogleAuthError("bad_nonce");
  if (typeof claims.sub !== "string" || !claims.sub) throw new GoogleAuthError("no_subject");
  if (typeof claims.email !== "string" || !claims.email) throw new GoogleAuthError("no_email");
  if (claims.email_verified !== true && claims.email_verified !== "true") throw new GoogleAuthError("email_not_verified");
  return { sub: claims.sub, email: claims.email.trim().toLowerCase() };
}

export async function exchangeCode(
  opts: { clientId: string; clientSecret: string; code: string; codeVerifier: string; redirectUri: string; nonce: string },
  fetcher: typeof fetch = fetch,
): Promise<GoogleIdentity> {
  if (!opts.clientId || !opts.clientSecret) throw new GoogleAuthError("not_configured");
  let res: Response;
  try {
    res = await fetcher(GOOGLE_TOKEN_URL, {
      method: "POST",
      headers: { "content-type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        grant_type: "authorization_code",
        code: opts.code,
        code_verifier: opts.codeVerifier,
        client_id: opts.clientId,
        client_secret: opts.clientSecret,
        redirect_uri: opts.redirectUri,
      }),
    });
  } catch {
    throw new GoogleAuthError("token_endpoint_unreachable");
  }
  if (!res.ok) throw new GoogleAuthError(`token_endpoint_${res.status}`);
  const data = (await res.json()) as { id_token?: unknown };
  if (typeof data.id_token !== "string") throw new GoogleAuthError("no_id_token");
  return validateIdTokenClaims(decodeJwtPayload(data.id_token), {
    clientId: opts.clientId,
    nonce: opts.nonce,
    nowSeconds: Math.floor(Date.now() / 1000),
  });
}
