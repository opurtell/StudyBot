const SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify";

export interface TurnstileResult {
  success: boolean;
  errorCodes: string[];
}

export async function verifyTurnstile(
  secret: string,
  token: string,
  remoteIp: string | undefined,
  idempotencyKey: string,
): Promise<TurnstileResult> {
  if (!secret) return { success: false, errorCodes: ["missing-input-secret"] };
  if (!token) return { success: false, errorCodes: ["missing-input-response"] };
  const body = new FormData();
  body.append("secret", secret);
  body.append("response", token);
  body.append("idempotency_key", idempotencyKey);
  if (remoteIp && remoteIp !== "unknown") body.append("remoteip", remoteIp);
  let res: Response;
  try {
    res = await fetch(SITEVERIFY_URL, { method: "POST", body });
  } catch {
    return { success: false, errorCodes: ["network-error"] };
  }
  if (!res.ok) return { success: false, errorCodes: [`http-${res.status}`] };
  const data = (await res.json()) as { success?: boolean; "error-codes"?: string[] };
  return { success: data.success === true, errorCodes: data["error-codes"] ?? [] };
}
