import { useCallback, useState } from "react";
import type { CorpusView } from "./api";
import { usePreferences } from "./preferences";

export type Qualification = "ap" | "icp";
export type QuizLevel = Qualification | "icp_only";

export interface ScopeChoice {
  level: Qualification | null;
  pacer: boolean;
}

export interface QuizScope {
  level: QuizLevel;
  pacer: boolean;
}

export const QUALIFICATION_OPTIONS: { value: Qualification; label: string }[] = [
  { value: "ap", label: "AP" },
  { value: "icp", label: "ICP" },
];

export const QUIZ_SCOPE_OPTIONS: { value: QuizLevel; label: string }[] = [
  { value: "ap", label: "AP" },
  { value: "icp", label: "ICP" },
  { value: "icp_only", label: "ICP only" },
];

export function viewFor(choice: { level: QuizLevel | null; pacer: boolean }): CorpusView {
  if (choice.level === null) return "icp_pacer";
  const base = choice.level === "ap" ? "ap" : "icp";
  return choice.pacer ? `${base}_pacer` : base;
}

export function quizScopeName(scope: QuizScope): string {
  const name = QUIZ_SCOPE_OPTIONS.find((o) => o.value === scope.level)?.label ?? "ICP";
  return `${name}${scope.pacer ? " + PACER" : ""}`;
}

export function useScopeChoice() {
  const { prefs, update } = usePreferences();
  const choice: ScopeChoice = { level: prefs.qualification, pacer: prefs.qualification ? prefs.pacer : false };
  const set = useCallback(
    (next: { level: Qualification; pacer: boolean }) => update({ ...prefs, qualification: next.level, pacer: next.pacer }),
    [prefs, update],
  );
  return [choice, set] as const;
}

const QUIZ_SCOPE_KEY = "quiz-scope";

export function defaultQuizScope(choice: ScopeChoice): QuizScope {
  return choice.level ? { level: choice.level, pacer: choice.pacer } : { level: "icp", pacer: true };
}

function basisOf(choice: ScopeChoice): string {
  return `${choice.level ?? "unset"}:${choice.pacer ? 1 : 0}`;
}

function loadQuizScope(basis: string): QuizScope | null {
  try {
    const saved = JSON.parse(localStorage.getItem(QUIZ_SCOPE_KEY) ?? "null") as { basis?: unknown; level?: unknown; pacer?: unknown } | null;
    if (!saved || saved.basis !== basis) return null;
    if (!QUIZ_SCOPE_OPTIONS.some((o) => o.value === saved.level) || typeof saved.pacer !== "boolean") return null;
    return { level: saved.level as QuizLevel, pacer: saved.pacer };
  } catch {
    return null;
  }
}

export function useQuizScope() {
  const [choice] = useScopeChoice();
  const basis = basisOf(choice);
  const [picked, setPicked] = useState<{ basis: string; scope: QuizScope | null }>(() => ({ basis, scope: loadQuizScope(basis) }));
  const scope = (picked.basis === basis ? picked.scope : loadQuizScope(basis)) ?? defaultQuizScope(choice);
  const set = useCallback(
    (next: QuizScope) => {
      setPicked({ basis, scope: next });
      try {
        localStorage.setItem(QUIZ_SCOPE_KEY, JSON.stringify({ basis, ...next }));
      } catch {
        return;
      }
    },
    [basis],
  );
  return [scope, set] as const;
}
