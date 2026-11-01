import type { Context } from "hono";
import type { ContentfulStatusCode } from "hono/utils/http-status";
import type { AppEnv } from "../types";

export type ErrorCode =
  | "bad_request"
  | "unauthorised"
  | "forbidden"
  | "forbidden_origin"
  | "unsupported_media_type"
  | "rate_limited"
  | "not_found"
  | "unavailable"
  | "internal_error";

export function apiError(c: Context<AppEnv>, status: ContentfulStatusCode, code: ErrorCode, message: string) {
  return c.json({ error: code, message, requestId: c.get("requestId") }, status);
}

export function clientIp(c: Context<AppEnv>): string {
  return c.req.header("cf-connecting-ip") ?? "unknown";
}
