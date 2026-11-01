import type { DocumentScope } from "../lib/api";

const LABELS: Record<DocumentScope, string> = { all: "AP", icp: "ICP only", pacer: "PACER only", mixed: "AP + ICP" };

const TONES: Record<DocumentScope, string> = {
  all: "bg-primary-fixed text-primary",
  mixed: "bg-surface-container-high text-on-surface-variant",
  icp: "bg-highlight text-on-highlight",
  pacer: "bg-highlight text-on-highlight",
};

export function ScopeBadge({ scope }: { scope: DocumentScope }) {
  return <span className={`rounded-sm px-2 py-0.5 font-mono text-[0.7rem] font-medium uppercase tracking-wide ${TONES[scope]}`}>{LABELS[scope]}</span>;
}
