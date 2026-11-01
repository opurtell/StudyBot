export const MODELS = {
  generation: "gemini-3.8-flash",
  marking: "gemini-3.5-flash-lite",
} as const;

export type ModelRole = keyof typeof MODELS;

export interface LlmRequest {
  role: ModelRole;
  system: string;
  user: string;
  maxOutputTokens?: number;
  responseSchema?: Record<string, unknown>;
  thinkingLevel?: "minimal" | "low" | "medium" | "high";
  metadata?: Record<string, string | number | boolean>;
}

export interface LlmUsage {
  inputTokens: number;
  outputTokens: number;
  thinkingTokens: number;
  cachedInputTokens: number;
}

export interface LlmResult {
  text: string;
  modelId: string;
  usage: LlmUsage;
  finishReason: string | null;
  latencyMs: number;
  gatewayLogId: string | null;
  cacheHit: boolean;
}

export class LlmError extends Error {
  constructor(
    message: string,
    readonly kind: "config" | "spend_limit" | "rate_limited" | "upstream" | "empty_response",
    readonly status?: number,
  ) {
    super(message);
    this.name = "LlmError";
  }
}

type GatewayEnv = Pick<Env, "AI_GATEWAY_ACCOUNT_ID" | "AI_GATEWAY_ID" | "GEMINI_API_KEY" | "AI_GATEWAY_TOKEN">;

export function gatewayUrl(env: GatewayEnv, modelId: string): string {
  if (!env.AI_GATEWAY_ACCOUNT_ID || !env.AI_GATEWAY_ID) {
    throw new LlmError("AI Gateway account or gateway ID is not configured", "config");
  }
  return `https://gateway.ai.cloudflare.com/v1/${env.AI_GATEWAY_ACCOUNT_ID}/${env.AI_GATEWAY_ID}/google-ai-studio/v1beta/models/${modelId}:generateContent`;
}

interface GeminiResponse {
  candidates?: { content?: { parts?: { text?: string; thought?: boolean }[] }; finishReason?: string }[];
  usageMetadata?: {
    promptTokenCount?: number;
    candidatesTokenCount?: number;
    thoughtsTokenCount?: number;
    cachedContentTokenCount?: number;
  };
}

export async function complete(env: GatewayEnv, req: LlmRequest, fetcher: typeof fetch = fetch): Promise<LlmResult> {
  if (!env.GEMINI_API_KEY) throw new LlmError("GEMINI_API_KEY is not configured", "config");
  const modelId = MODELS[req.role];
  const generationConfig: Record<string, unknown> = { maxOutputTokens: req.maxOutputTokens ?? 1024 };
  if (req.responseSchema) {
    generationConfig.responseMimeType = "application/json";
    generationConfig.responseJsonSchema = req.responseSchema;
  }
  if (req.thinkingLevel) generationConfig.thinkingConfig = { thinkingLevel: req.thinkingLevel };

  const headers: Record<string, string> = {
    "content-type": "application/json",
    "x-goog-api-key": env.GEMINI_API_KEY,
  };
  if (env.AI_GATEWAY_TOKEN) headers["cf-aig-authorization"] = `Bearer ${env.AI_GATEWAY_TOKEN}`;
  if (req.metadata) headers["cf-aig-metadata"] = JSON.stringify(req.metadata);

  const started = Date.now();
  const res = await fetcher(gatewayUrl(env, modelId), {
    method: "POST",
    headers,
    body: JSON.stringify({
      systemInstruction: { parts: [{ text: req.system }] },
      contents: [{ role: "user", parts: [{ text: req.user }] }],
      generationConfig,
    }),
  });
  const latencyMs = Date.now() - started;

  if (!res.ok) {
    const detail = (await res.text()).slice(0, 500);
    if (res.status === 429) {
      const kind = /spend|budget/i.test(detail) ? "spend_limit" : "rate_limited";
      throw new LlmError(`AI Gateway refused the request (${kind})`, kind, 429);
    }
    throw new LlmError(`Gemini request failed with ${res.status}: ${detail}`, "upstream", res.status);
  }

  const data = (await res.json()) as GeminiResponse;
  const candidate = data.candidates?.[0];
  const text = (candidate?.content?.parts ?? [])
    .filter((p) => !p.thought && typeof p.text === "string")
    .map((p) => p.text)
    .join("")
    .trim();
  if (!text) throw new LlmError("Gemini returned no text", "empty_response");

  const usage = data.usageMetadata ?? {};
  return {
    text,
    modelId,
    usage: {
      inputTokens: usage.promptTokenCount ?? 0,
      outputTokens: usage.candidatesTokenCount ?? 0,
      thinkingTokens: usage.thoughtsTokenCount ?? 0,
      cachedInputTokens: usage.cachedContentTokenCount ?? 0,
    },
    finishReason: candidate?.finishReason ?? null,
    latencyMs,
    gatewayLogId: res.headers.get("cf-aig-log-id"),
    cacheHit: res.headers.get("cf-aig-cache-status") === "HIT",
  };
}
