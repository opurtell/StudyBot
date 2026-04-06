import type { QuizAttempt } from "../types/api";
import AdaptiveText from "./AdaptiveText";

interface RecentEntriesProps {
  entries: QuizAttempt[];
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-AU", { day: "2-digit", month: "short" });
}

function scoreColour(score: string | null): string {
  switch (score) {
    case "correct": return "text-emerald-600";
    case "partial": return "text-amber-600";
    case "incorrect": return "text-rose-600";
    default: return "text-on-surface-variant";
  }
}

export default function RecentEntries({ entries }: RecentEntriesProps) {
  if (entries.length === 0) {
    return (
      <p className="font-body text-body-md text-on-surface-variant italic">
        No recent quiz attempts.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {entries.map((entry) => (
        <div
          key={entry.id}
          className="flex items-center gap-6 py-3 hover:bg-surface-container-lowest transition-colors px-2"
        >
          <span className="font-mono text-[10px] text-on-surface-variant w-20 shrink-0">
            {formatDate(entry.created_at)}
          </span>
          <div className="flex-1 min-w-0">
            <AdaptiveText
              text={entry.category}
              variant="title"
              className="text-on-surface"
            />
            <p className="font-body text-body-md text-on-surface-variant">
              {entry.question_type} — {entry.source_citation}
            </p>
          </div>
          <span className={`font-label text-label-sm uppercase ${scoreColour(entry.score)}`}>
            {entry.score ?? "skipped"}
          </span>
        </div>
      ))}
    </div>
  );
}
