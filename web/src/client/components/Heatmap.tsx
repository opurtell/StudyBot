import { Link } from "react-router";
import type { MasteryStatus, SectionMastery } from "../lib/api";

const STATUS: Record<MasteryStatus, { label: string; dot: string; bar: string }> = {
  strong: { label: "Strong", dot: "bg-emerald-600", bar: "bg-emerald-600" },
  developing: { label: "Developing", dot: "bg-amber-400", bar: "bg-amber-400" },
  weak: { label: "Needs work", dot: "bg-rose-500", bar: "bg-rose-500" },
  new: { label: "Not started", dot: "bg-outline-variant", bar: "bg-outline-variant" },
};

export function quizLink(section: string, documentId?: string | null): string {
  const params = new URLSearchParams(documentId ? { document: documentId } : { section });
  return `/quiz?${params.toString()}`;
}

export function Heatmap({ sections }: { sections: SectionMastery[] }) {
  if (sections.length === 0) return <p className="text-sm text-on-surface-variant">No topics are available for your scope yet.</p>;
  return (
    <ul className="grid grid-cols-2 gap-2 sm:grid-cols-3 sm:gap-3" aria-label="Knowledge heatmap">
      {sections.map((s) => {
        const status = STATUS[s.status];
        const weakest = s.status !== "new" && s.status !== "strong" ? s.documents[0] : undefined;
        return (
          <li key={s.section}>
            <Link
              to={quizLink(s.section)}
              className="flex h-full min-h-32 flex-col justify-between gap-3 rounded-sm bg-surface-container-low p-3 hover:bg-surface-container sm:p-4"
            >
              <span className="flex items-start justify-between gap-2">
                <span className="font-headline text-lg font-semibold leading-tight">{s.section}</span>
                <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${status.dot}`} aria-hidden="true" />
              </span>
              <span className="space-y-1">
                <span className="block text-sm">
                  {s.percent === null ? status.label : `${Math.round(s.percent)}% · ${status.label}`}
                </span>
                <span className="block font-mono text-xs text-on-surface-variant">
                  {s.answered} answered{s.questions ? ` of ${s.questions}` : ""}
                </span>
                {weakest && <span className="block text-xs text-on-surface-variant">Weakest: {weakest.title}</span>}
              </span>
              <span
                className="block h-1 w-full bg-outline-variant/30"
                role="progressbar"
                aria-label={`${s.section} mastery`}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={s.percent ?? 0}
              >
                <span className={`block h-full ${status.bar}`} style={{ width: `${s.percent ?? 0}%` }} />
              </span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
