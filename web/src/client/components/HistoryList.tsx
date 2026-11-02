import { Link } from "react-router";
import type { Score } from "../lib/api";
import { SCORE_CLASS, SCORE_LABEL, SELF_LABEL } from "./Feedback";

export interface HistoryEntry {
  id: string;
  questionText: string;
  documentTitle: string;
  kind: "marked" | "revealed";
  score: Score | null;
  at: number;
  href?: string;
}

const dateFormat = new Intl.DateTimeFormat("en-AU", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });

function Result({ entry }: { entry: HistoryEntry }) {
  if (!entry.score) return <span className="text-xs text-on-surface-variant">Reference revealed</span>;
  return (
    <span className={`rounded-sm px-2 py-0.5 text-xs font-semibold ${SCORE_CLASS[entry.score]}`}>
      {entry.kind === "marked" ? SCORE_LABEL[entry.score] : `Self: ${SELF_LABEL[entry.score]}`}
    </span>
  );
}

export function HistoryList({ entries }: { entries: HistoryEntry[] }) {
  return (
    <ol className="space-y-2">
      {entries.map((e) => {
        const body = (
          <>
            <span className="block text-sm font-medium leading-snug">{e.questionText}</span>
            <span className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-on-surface-variant">
              <Result entry={e} />
              <span>{e.documentTitle}</span>
              <time dateTime={new Date(e.at).toISOString()}>{dateFormat.format(e.at)}</time>
            </span>
          </>
        );
        return (
          <li key={e.id}>
            {e.href ? (
              <Link to={e.href} className="block rounded-sm bg-surface-container-lowest p-3 hover:bg-surface-container">
                {body}
              </Link>
            ) : (
              <div className="rounded-sm bg-surface-container-lowest p-3">{body}</div>
            )}
          </li>
        );
      })}
    </ol>
  );
}
