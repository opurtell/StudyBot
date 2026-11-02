import { useCallback, useEffect, useState } from "react";
import type { ProgressRow, Score } from "../../shared/progress";
import type { ImportAttempt } from "./api";

const KEY = "guest-progress";
const MAX_RECORDS = 1000;
const EVENT = "guest-progress-changed";

export interface GuestAttempt {
  id: string;
  questionId: string;
  questionText: string;
  documentId: string;
  documentTitle: string;
  section: string;
  score: Score | null;
  at: number;
}

function valid(item: unknown): item is GuestAttempt {
  if (!item || typeof item !== "object") return false;
  const a = item as Record<string, unknown>;
  return (
    typeof a.id === "string" &&
    typeof a.questionId === "string" &&
    typeof a.documentId === "string" &&
    typeof a.section === "string" &&
    typeof a.at === "number" &&
    (a.score === null || a.score === "correct" || a.score === "partial" || a.score === "incorrect")
  );
}

export function loadGuestAttempts(): GuestAttempt[] {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) ?? "[]") as unknown;
    return Array.isArray(raw) ? raw.filter(valid) : [];
  } catch {
    return [];
  }
}

function save(list: GuestAttempt[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(list.slice(-MAX_RECORDS)));
  } catch {
    return;
  }
  window.dispatchEvent(new Event(EVENT));
}

export function recordGuestAttempt(attempt: Omit<GuestAttempt, "id" | "at">): string {
  const id = `g-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
  save([...loadGuestAttempts(), { ...attempt, id, at: Date.now() }]);
  return id;
}

export function gradeGuestAttempt(id: string, score: Score) {
  save(loadGuestAttempts().map((a) => (a.id === id ? { ...a, score } : a)));
}

export function clearGuestAttempts() {
  try {
    localStorage.removeItem(KEY);
  } catch {
    return;
  }
  window.dispatchEvent(new Event(EVENT));
}

export function toProgressRows(list: GuestAttempt[]): ProgressRow[] {
  return list.map((a) => ({
    questionId: a.questionId,
    documentId: a.documentId,
    documentTitle: a.documentTitle,
    section: a.section,
    score: a.score,
    at: a.at,
  }));
}

export function toImport(list: GuestAttempt[]): ImportAttempt[] {
  return list.map((a) => ({ questionId: a.questionId, score: a.score, at: Math.round(a.at) }));
}

export function useGuestAttempts() {
  const [list, setList] = useState<GuestAttempt[]>(loadGuestAttempts);
  useEffect(() => {
    const reload = () => setList(loadGuestAttempts());
    window.addEventListener(EVENT, reload);
    window.addEventListener("storage", reload);
    return () => {
      window.removeEventListener(EVENT, reload);
      window.removeEventListener("storage", reload);
    };
  }, []);
  const clear = useCallback(() => clearGuestAttempts(), []);
  return { attempts: list, clear };
}
