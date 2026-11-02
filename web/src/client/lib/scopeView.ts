import { useCallback } from "react";
import type { CorpusView } from "./api";
import { usePreferences } from "./preferences";

export type ScopeLevel = "all" | "ap" | "icp";

export interface ScopeChoice {
  level: ScopeLevel;
  pacer: boolean;
}

export function viewFor(choice: ScopeChoice): CorpusView {
  if (choice.level === "all") return "icp_pacer";
  return choice.pacer ? `${choice.level}_pacer` : choice.level;
}

export function useScopeChoice() {
  const { prefs, update } = usePreferences();
  const choice: ScopeChoice = { level: prefs.qualification ?? "all", pacer: prefs.qualification ? prefs.pacer : false };
  const set = useCallback(
    (next: ScopeChoice) => update({ ...prefs, qualification: next.level === "all" ? null : next.level, pacer: next.pacer }),
    [prefs, update],
  );
  return [choice, set] as const;
}
