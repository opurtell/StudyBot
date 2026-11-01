import type { CorpusView } from "../corpus/repo";
import prompts from "./prompts.json";

export const PROMPT_VERSION: string = prompts.promptVersion;
export const EVALUATION_SYSTEM: string = prompts.evaluationSystem;
export const EVALUATION_SCHEMA: Record<string, unknown> = prompts.evaluationSchema;
export const GENERATION_SCHEMA: Record<string, unknown> = prompts.generationSchema;

export const DIFFICULTIES = ["easy", "medium", "hard"] as const;
export type Difficulty = (typeof DIFFICULTIES)[number];
export const QUESTION_TYPES = ["recall", "definition", "scenario", "drug_dose"] as const;
export type QuestionType = (typeof QUESTION_TYPES)[number];
export const SCORES = ["correct", "partial", "incorrect"] as const;
export type Score = (typeof SCORES)[number];

export const SOURCE_LABEL = "guideline";

export function generationSystem(view: CorpusView): string {
  return view === "icp" || view === "icp_pacer" ? prompts.generationSystem.icp : prompts.generationSystem.ap;
}

export function generationUser(sources: string[], difficulty: Difficulty, previous: string[] = []): string {
  const sourceText = sources.map((text, i) => `[Source ${i + 1}: ${SOURCE_LABEL}]\n${text}`).join("\n\n");
  let user = `Source material:\n\n${sourceText}\n\nDifficulty: ${difficulty}`;
  const extra = prompts.difficultyInstructions[difficulty];
  if (extra) user += `\n\n${extra}`;
  if (previous.length > 0) {
    user += `\n\nPreviously asked questions (do NOT repeat these):\n${previous.map((q) => `- ${q}`).join("\n")}`;
  }
  return user;
}

export function markingUser(question: string, source: string, answer: string): string {
  return `Question: ${question}\n\nSource material:\n${source}\n\nStudent answer: ${answer}`;
}

export function parseJsonObject(text: string): Record<string, unknown> | null {
  if (!text) return null;
  const fenced = /```(?:json)?\s+([\s\S]*?)\s+```/.exec(text);
  const body = (fenced?.[1] ?? text).trim();
  const attempt = (raw: string): unknown => {
    try {
      return JSON.parse(raw);
    } catch {
      return undefined;
    }
  };
  let parsed = attempt(body);
  if (parsed === undefined) {
    const braces = /(\{[\s\S]*\})/.exec(body);
    if (braces?.[1]) parsed = attempt(braces[1].trim());
  }
  return parsed !== null && typeof parsed === "object" && !Array.isArray(parsed) ? (parsed as Record<string, unknown>) : null;
}

export interface ParsedGeneration {
  questionText: string;
  questionType: QuestionType;
  sourceCitation: string | null;
  category: string | null;
  sourceIndex: number;
}

export function parseGeneration(text: string, sourceCount: number): ParsedGeneration | null {
  const parsed = parseJsonObject(text);
  if (!parsed) return null;
  const questionText = typeof parsed.question_text === "string" ? parsed.question_text.trim() : "";
  if (questionText.length < 10) return null;
  const type = parsed.question_type;
  let index = typeof parsed.source_index === "number" ? parsed.source_index : Number.parseInt(String(parsed.source_index ?? ""), 10);
  if (!Number.isFinite(index)) index = 1;
  const clamped = Math.max(0, Math.min(Math.trunc(index) - 1, sourceCount - 1));
  const optional = (value: unknown) => (typeof value === "string" && value.trim() ? value.trim() : null);
  return {
    questionText,
    questionType: (QUESTION_TYPES as readonly unknown[]).includes(type) ? (type as QuestionType) : "recall",
    sourceCitation: optional(parsed.source_citation),
    category: optional(parsed.category),
    sourceIndex: clamped,
  };
}

export interface Evaluation {
  score: Score;
  correctElements: string[];
  missingOrWrong: string[];
  sourceQuote: string;
  feedbackSummary: string;
}

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.map((v) => String(v)) : [];
}

export function parseEvaluation(text: string): Evaluation | null {
  const parsed = parseJsonObject(text);
  if (!parsed) return null;
  const score = parsed.score;
  if (typeof score !== "string" || !(SCORES as readonly string[]).includes(score)) return null;
  return {
    score: score as Score,
    correctElements: stringList(parsed.correct_elements),
    missingOrWrong: stringList(parsed.missing_or_wrong),
    sourceQuote: parsed.source_quote ? String(parsed.source_quote) : "",
    feedbackSummary: parsed.feedback_summary ? String(parsed.feedback_summary) : "",
  };
}
