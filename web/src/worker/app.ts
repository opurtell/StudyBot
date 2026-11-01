import { Hono } from "hono";
import { authRoutes, meRoutes } from "./auth/routes";
import { loadSession } from "./auth/sessions";
import { apiError, clientIp } from "./lib/http";
import { createLogger } from "./lib/log";
import type { AppEnv } from "./types";

const MUTATING_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);
const MAX_JSON_BYTES = 16 * 1024;

export const app = new Hono<AppEnv>().basePath("/api");

app.use("*", async (c, next) => {
  const requestId = c.req.header("cf-ray") ?? crypto.randomUUID();
  const started = Date.now();
  const log = createLogger({ requestId, env: c.env.ENVIRONMENT, method: c.req.method, path: new URL(c.req.url).pathname });
  c.set("requestId", requestId);
  c.set("log", log);
  c.set("user", null);
  c.set("sessionHash", null);
  await next();
  c.header("Cache-Control", "no-store");
  c.header("X-Content-Type-Options", "nosniff");
  c.header("X-Request-Id", requestId);
  log.info("request", { status: c.res.status, durationMs: Date.now() - started, userId: c.get("user")?.id ?? null });
});

app.use("*", async (c, next) => {
  const { success } = await c.env.RL_API.limit({ key: `ip:${clientIp(c)}` });
  if (!success) return apiError(c, 429, "rate_limited", "Too many requests. Wait a minute and try again.");
  await next();
});

app.use("*", async (c, next) => {
  if (MUTATING_METHODS.has(c.req.method)) {
    const origin = c.req.header("origin");
    if (!origin || origin !== new URL(c.req.url).origin) {
      return apiError(c, 403, "forbidden_origin", "Cross-site requests are not allowed.");
    }
    const hasBody = c.req.method !== "DELETE" || c.req.header("content-length") !== undefined;
    if (hasBody && !c.req.header("content-type")?.toLowerCase().startsWith("application/json")) {
      return apiError(c, 415, "unsupported_media_type", "Send JSON.");
    }
    const length = Number(c.req.header("content-length") ?? "0");
    if (length > MAX_JSON_BYTES) return apiError(c, 400, "bad_request", "Request body is too large.");
  }
  await next();
});

app.use("*", async (c, next) => {
  const session = await loadSession(c);
  if (session) {
    c.set("user", session.user);
    c.set("sessionHash", session.idHash);
  }
  await next();
});

app.get("/health", (c) => c.json({ ok: true, environment: c.env.ENVIRONMENT }));

app.get("/config", (c) =>
  c.json({
    environment: c.env.ENVIRONMENT,
    devSignIn: c.env.ENVIRONMENT === "development" && ["localhost", "127.0.0.1"].includes(new URL(c.req.url).hostname),
  }),
);

app.route("/auth", authRoutes);
app.route("/me", meRoutes);

app.notFound((c) => apiError(c, 404, "not_found", "No such endpoint."));

app.onError((err, c) => {
  const log = c.get("log") ?? createLogger({ path: new URL(c.req.url).pathname });
  log.error("unhandled_error", { err });
  return apiError(c, 500, "internal_error", "Something went wrong. Try again shortly.");
});
