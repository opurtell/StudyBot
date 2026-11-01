import { useCallback, useState } from "react";
import type { CorpusView } from "./api";

export type ScopeLevel = "all" | "ap" | "icp";

export interface ScopeChoice {
  level: ScopeLevel;
  pacer: boolean;
}

const STORAGE_KEY = "scope-view";
const DEFAULT_CHOICE: ScopeChoice = { level: "all", pacer: false };

export function viewFor(choice: ScopeChoice): CorpusView {
  if (choice.level === "all") return "icp_pacer";
  return choice.pacer ? `${choice.level}_pacer` : choice.level;
}

function load(): ScopeChoice {
  try {
    const raw = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "null") as Partial<ScopeChoice> | null;
    if (raw && (raw.level === "all" || raw.level === "ap" || raw.level === "icp")) {
      return { level: raw.level, pacer: raw.pacer === true };
    }
  } catch {
    return DEFAULT_CHOICE;
  }
  return DEFAULT_CHOICE;
}

export function useScopeChoice() {
  const [choice, setChoice] = useState<ScopeChoice>(load);
  const update = useCallback((next: ScopeChoice) => {
    setChoice(next);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {
      return;
    }
  }, []);
  return [choice, update] as const;
}
