export type Score = "correct" | "partial" | "incorrect";

export interface RubricCite {
  chunkId: string;
  documentId: string;
  quote: string;
}

export interface RubricPoint {
  point: string;
  critical: boolean;
  cites: RubricCite[];
}

export const PATIENT_GROUPS = ["adult", "paediatric", "neonate", "obstetric", "older_adult"] as const;
export type PatientGroup = (typeof PATIENT_GROUPS)[number];

export const PATIENT_GROUP_LABELS: Record<PatientGroup, string> = {
  adult: "Adult",
  paediatric: "Paediatric",
  neonate: "Neonate",
  obstetric: "Obstetric",
  older_adult: "Older adult",
};

export function stageScore(rubric: { critical: boolean }[], ticked: readonly number[]): Score {
  const got = new Set(ticked);
  const critical = rubric.map((p, i) => (p.critical ? i : -1)).filter((i) => i >= 0);
  if (critical.some((i) => !got.has(i))) return "incorrect";
  const others = rubric.map((p, i) => (p.critical ? -1 : i)).filter((i) => i >= 0);
  const covered = others.filter((i) => got.has(i)).length;
  return covered * 2 >= others.length ? "correct" : "partial";
}

export function scenarioScore(stages: readonly Score[]): Score {
  if (stages.length === 0) return "incorrect";
  if (stages.every((s) => s === "correct")) return "correct";
  const wrong = stages.filter((s) => s === "incorrect").length;
  return wrong * 2 > stages.length ? "incorrect" : "partial";
}
