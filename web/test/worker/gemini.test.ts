import { describe, expect, it, vi } from "vitest";
import { complete, gatewayUrl, LlmError, MODELS } from "../../src/worker/llm/gemini";

const gatewayEnv = {
  AI_GATEWAY_ACCOUNT_ID: "acct123",
  AI_GATEWAY_ID: "studybot-test",
  GEMINI_API_KEY: "gem-key",
  AI_GATEWAY_TOKEN: "gw-token",
};

function okResponse(body: unknown, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json", ...headers } });
}

describe("Gemini via AI Gateway", () => {
  it("uses the signed-off models", () => {
    expect(MODELS).toEqual({ generation: "gemini-3.8-flash", marking: "gemini-3.5-flash-lite" });
  });

  it("builds the AI Gateway URL for Google AI Studio", () => {
    expect(gatewayUrl(gatewayEnv, "gemini-3.5-flash-lite")).toBe(
      "https://gateway.ai.cloudflare.com/v1/acct123/studybot-test/google-ai-studio/v1beta/models/gemini-3.5-flash-lite:generateContent",
    );
  });

  it("refuses to run without gateway config", () => {
    expect(() => gatewayUrl({ ...gatewayEnv, AI_GATEWAY_ACCOUNT_ID: "" }, "m")).toThrow(LlmError);
  });

  it("sends keys in headers and returns text plus token usage", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
      okResponse(
        {
          candidates: [{ content: { parts: [{ text: "thinking...", thought: true }, { text: '{"score":"correct"}' }] }, finishReason: "STOP" }],
          usageMetadata: { promptTokenCount: 812, candidatesTokenCount: 140, thoughtsTokenCount: 30, cachedContentTokenCount: 600 },
        },
        { "cf-aig-log-id": "log-1", "cf-aig-cache-status": "MISS" },
      ),
    );
    const result = await complete(
      gatewayEnv,
      { role: "marking", system: "sys", user: "answer", responseSchema: { type: "object" }, thinkingLevel: "minimal", metadata: { userId: "u1" } },
      fetcher,
    );
    expect(result).toMatchObject({
      text: '{"score":"correct"}',
      modelId: "gemini-3.5-flash-lite",
      usage: { inputTokens: 812, outputTokens: 140, thinkingTokens: 30, cachedInputTokens: 600 },
      finishReason: "STOP",
      gatewayLogId: "log-1",
      cacheHit: false,
    });
    const [url, init] = fetcher.mock.calls[0];
    expect(String(url)).toContain("/models/gemini-3.5-flash-lite:generateContent");
    const headers = init?.headers as Record<string, string>;
    expect(headers["x-goog-api-key"]).toBe("gem-key");
    expect(headers["cf-aig-authorization"]).toBe("Bearer gw-token");
    expect(JSON.parse(headers["cf-aig-metadata"])).toEqual({ userId: "u1" });
    const sent = JSON.parse(String(init?.body));
    expect(sent.systemInstruction.parts[0].text).toBe("sys");
    expect(sent.generationConfig).toMatchObject({
      responseMimeType: "application/json",
      responseJsonSchema: { type: "object" },
      thinkingConfig: { thinkingLevel: "minimal" },
    });
  });

  it("reports an AI Gateway spend limit distinctly", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response("Spend limit exceeded for this gateway", { status: 429 }));
    await expect(complete(gatewayEnv, { role: "generation", system: "s", user: "u" }, fetcher)).rejects.toMatchObject({
      kind: "spend_limit",
      status: 429,
    });
  });

  it("treats an empty candidate as an error, not a blank answer", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(okResponse({ candidates: [{ content: { parts: [] } }] }));
    await expect(complete(gatewayEnv, { role: "marking", system: "s", user: "u" }, fetcher)).rejects.toMatchObject({
      kind: "empty_response",
    });
  });

  it("refuses to call out without an API key", async () => {
    const fetcher = vi.fn<typeof fetch>();
    await expect(complete({ ...gatewayEnv, GEMINI_API_KEY: "" }, { role: "marking", system: "s", user: "u" }, fetcher)).rejects.toMatchObject({
      kind: "config",
    });
    expect(fetcher).not.toHaveBeenCalled();
  });
});
