import { afterEach, describe, expect, it, vi } from "vitest";
import { createLogger } from "../../src/worker/lib/log";
import { currentQuotaPeriod, summariseQuota } from "../../src/worker/lib/quota";
import { purgeExpired } from "../../src/worker/auth/sessions";
import { env } from "cloudflare:workers";

afterEach(() => vi.restoreAllMocks());

describe("quota summary", () => {
  const limits = { QUOTA_GENERATIONS_PER_MONTH: "20", QUOTA_MARKS_PER_MONTH: "30" };
  const now = new Date("2026-11-15T00:00:00Z");

  it("uses the stored counters within the same month", () => {
    const q = summariseQuota(limits, { quotaPeriod: "2026-11", freeGenUsed: 5, freeEvalUsed: 31 }, now);
    expect(q.generations).toEqual({ used: 5, limit: 20, remaining: 15 });
    expect(q.marking).toEqual({ used: 31, limit: 30, remaining: 0 });
  });

  it("treats counters from a previous month as reset", () => {
    const q = summariseQuota(limits, { quotaPeriod: "2026-10", freeGenUsed: 20, freeEvalUsed: 30 }, now);
    expect(q.period).toBe("2026-11");
    expect(q.generations.remaining).toBe(20);
    expect(q.marking.remaining).toBe(30);
  });

  it("falls back to the default limits when config is malformed", () => {
    const q = summariseQuota({ QUOTA_GENERATIONS_PER_MONTH: "lots", QUOTA_MARKS_PER_MONTH: "" }, { quotaPeriod: "2026-11", freeGenUsed: 0, freeEvalUsed: 0 }, now);
    expect(q.generations.limit).toBe(20);
    expect(q.marking.limit).toBe(30);
  });

  it("formats the period as UTC year-month", () => {
    expect(currentQuotaPeriod(new Date("2026-12-31T23:59:59Z"))).toBe("2026-12");
  });
});

describe("structured logger", () => {
  it("writes one JSON line with base fields and redacts personal data", () => {
    const spy = vi.spyOn(console, "log").mockImplementation(() => {});
    createLogger({ requestId: "r1" }).child({ path: "/api/x" }).info("hello", { email: "a@b.com", token: "t", status: 200 });
    const record = JSON.parse(spy.mock.calls[0][0] as string);
    expect(record).toEqual({ level: "info", msg: "hello", requestId: "r1", path: "/api/x", email: "[redacted]", token: "[redacted]", status: 200 });
  });

  it("serialises errors at error level", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    createLogger().error("boom", { err: new TypeError("bad") });
    const record = JSON.parse(spy.mock.calls[0][0] as string);
    expect(record).toMatchObject({ level: "error", msg: "boom", errName: "TypeError", errMessage: "bad" });
  });
});

describe("purgeExpired", () => {
  it("removes expired sessions only", async () => {
    const now = Date.now();
    const userId = crypto.randomUUID();
    await env.DB.batch([
      env.DB.prepare("INSERT INTO users (id, google_sub, email, quota_period, created_at) VALUES (?, ?, ?, '2026-11', ?)").bind(userId, userId, `${userId}@example.com`, now),
      env.DB.prepare("INSERT INTO sessions VALUES ('old', ?, ?, ?, ?)").bind(userId, now, now - 1, now),
      env.DB.prepare("INSERT INTO sessions VALUES ('live', ?, ?, ?, ?)").bind(userId, now, now + 60_000, now),
    ]);
    await purgeExpired(env.DB, now);
    const sessions = await env.DB.prepare("SELECT id_hash FROM sessions WHERE user_id = ?").bind(userId).all<{ id_hash: string }>();
    expect(sessions.results.map((r) => r.id_hash)).toEqual(["live"]);
  });
});
