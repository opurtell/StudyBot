import type { DocumentScope } from "../lib/api";

const LABELS: Partial<Record<DocumentScope, string>> = { icp: "ICP only", pacer: "PACER only", mixed: "AP + ICP" };

export function ScopeBadge({ scope }: { scope: DocumentScope }) {
  const label = LABELS[scope];
  if (!label) return null;
  const tone = scope === "mixed" ? "bg-surface-container-high text-on-surface-variant" : "bg-highlight text-on-highlight";
  return <span className={`rounded-sm px-2 py-0.5 font-mono text-[0.7rem] font-medium uppercase tracking-wide ${tone}`}>{label}</span>;
}
