export type Score = "correct" | "partial" | "incorrect";
export type MasteryStatus = "strong" | "developing" | "weak" | "new";

export interface ProgressRow {
  questionId: string;
  documentId: string;
  documentTitle: string;
  section: string;
  score: Score | null;
  at: number;
}

export interface TopicDocument {
  id: string;
  kind: "cmg" | "csm" | "med";
  number: string;
  title: string;
  questions: number;
}

export interface Topic {
  section: string;
  questions: number;
  documents: TopicDocument[];
}

export interface MasteryCell {
  answered: number;
  correct: number;
  partial: number;
  incorrect: number;
  percent: number | null;
  status: MasteryStatus;
}

export interface DocumentMastery extends MasteryCell {
  id: string;
  title: string;
}

export interface SectionMastery extends MasteryCell {
  section: string;
  questions: number;
  documents: DocumentMastery[];
}

export interface ProgressSummary {
  sections: SectionMastery[];
  totals: {
    answered: number;
    accuracy: number | null;
    streakDays: number;
    studiedToday: boolean;
  };
  weakest: { section: string; documentId: string | null; documentTitle: string | null } | null;
}

const DAY_MS = 86_400_000;

export function masteryStatus(percent: number | null): MasteryStatus {
  if (percent === null) return "new";
  if (percent > 75) return "strong";
  if (percent >= 50) return "developing";
  return "weak";
}

function cell(scores: Score[]): MasteryCell {
  const correct = scores.filter((s) => s === "correct").length;
  const partial = scores.filter((s) => s === "partial").length;
  const incorrect = scores.length - correct - partial;
  const percent = scores.length === 0 ? null : Math.round(((correct + partial * 0.5) / scores.length) * 1000) / 10;
  return { answered: scores.length, correct, partial, incorrect, percent, status: masteryStatus(percent) };
}

export function localDay(at: number, tzOffsetMinutes: number): number {
  return Math.floor((at - tzOffsetMinutes * 60_000) / DAY_MS);
}

export function latestScored(rows: ProgressRow[]): ProgressRow[] {
  const latest = new Map<string, ProgressRow>();
  for (const row of rows) {
    if (!row.score) continue;
    const prev = latest.get(row.questionId);
    if (!prev || row.at >= prev.at) latest.set(row.questionId, row);
  }
  return [...latest.values()];
}

export function streakDays(rows: ProgressRow[], now: number, tzOffsetMinutes: number): { days: number; today: boolean } {
  const days = new Set(rows.map((r) => localDay(r.at, tzOffsetMinutes)));
  const today = localDay(now, tzOffsetMinutes);
  let day = days.has(today) ? today : today - 1;
  let count = 0;
  while (days.has(day)) {
    count += 1;
    day -= 1;
  }
  return { days: count, today: days.has(today) };
}

export function summariseProgress(
  rows: ProgressRow[],
  topics: Topic[],
  opts: { now: number; tzOffsetMinutes: number },
): ProgressSummary {
  const scored = latestScored(rows);
  const bySection = new Map<string, ProgressRow[]>();
  for (const row of scored) {
    const list = bySection.get(row.section) ?? [];
    list.push(row);
    bySection.set(row.section, list);
  }

  const names = new Set<string>([...topics.map((t) => t.section), ...bySection.keys()]);
  const sections: SectionMastery[] = [...names]
    .sort((a, b) => a.localeCompare(b))
    .map((section) => {
      const topic = topics.find((t) => t.section === section);
      const sectionRows = bySection.get(section) ?? [];
      const byDoc = new Map<string, ProgressRow[]>();
      for (const row of sectionRows) {
        const list = byDoc.get(row.documentId) ?? [];
        list.push(row);
        byDoc.set(row.documentId, list);
      }
      const documents: DocumentMastery[] = [...byDoc.entries()]
        .map(([id, list]) => ({ id, title: list[0]!.documentTitle, ...cell(list.map((r) => r.score as Score)) }))
        .sort((a, b) => (a.percent ?? 0) - (b.percent ?? 0) || b.answered - a.answered);
      return {
        section,
        questions: topic?.questions ?? 0,
        documents,
        ...cell(sectionRows.map((r) => r.score as Score)),
      };
    });

  const all = cell(scored.map((r) => r.score as Score));
  const streak = streakDays(rows, opts.now, opts.tzOffsetMinutes);
  const answeredSections = sections.filter((s) => s.percent !== null);
  const weakestSection = answeredSections.sort((a, b) => (a.percent ?? 0) - (b.percent ?? 0) || b.answered - a.answered)[0];
  const weakestDoc = weakestSection?.documents[0];

  return {
    sections,
    totals: {
      answered: all.answered,
      accuracy: all.answered === 0 ? null : Math.round((all.correct / all.answered) * 1000) / 10,
      streakDays: streak.days,
      studiedToday: streak.today,
    },
    weakest: weakestSection
      ? { section: weakestSection.section, documentId: weakestDoc?.id ?? null, documentTitle: weakestDoc?.title ?? null }
      : null,
  };
}
