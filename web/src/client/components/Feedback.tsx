import { Link } from "react-router";
import type { Score } from "../lib/api";

export const SCORE_LABEL: Record<Score, string> = { correct: "Correct", partial: "Partly correct", incorrect: "Incorrect" };
export const SCORE_CLASS: Record<Score, string> = {
  correct: "bg-primary text-on-primary",
  partial: "bg-highlight text-on-highlight",
  incorrect: "bg-error text-white",
};
export const SELF_LABEL: Record<Score, string> = { correct: "Got it", partial: "Partly", incorrect: "Missed it" };

export function ScoreBadge({ score, self = false }: { score: Score; self?: boolean }) {
  return (
    <span className={`inline-block rounded-sm px-2 py-1 text-sm font-semibold ${SCORE_CLASS[score]}`}>
      {self ? `Self-marked: ${SELF_LABEL[score]}` : SCORE_LABEL[score]}
    </span>
  );
}

export function documentPath(documentId: string): string {
  return `/${documentId.startsWith("MED_") ? "medications" : "guidelines"}/${encodeURIComponent(documentId)}`;
}

export interface FeedbackData {
  marked: boolean;
  score: Score | null;
  feedbackSummary?: string;
  correctElements?: string[];
  missingOrWrong?: string[];
  sourceQuote?: string;
  sourceText: string;
  citation: string;
  documentId: string;
  documentTitle: string;
}

function List({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div>
      <h3 className="text-sm font-semibold">{title}</h3>
      <ul className="list-disc pl-5 text-sm">
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

function Source({ data }: { data: FeedbackData }) {
  return (
    <div className="space-y-2 rounded-sm bg-surface-container-low p-4">
      <h3 className="text-sm font-semibold">From the source</h3>
      <p className="whitespace-pre-wrap text-sm">{data.sourceText}</p>
      <p className="text-xs text-on-surface-variant">
        Ref: {data.citation} ·{" "}
        <Link to={documentPath(data.documentId)} className="underline">
          Read {data.documentTitle}
        </Link>
      </p>
    </div>
  );
}

export function Feedback({ data, answer }: { data: FeedbackData; answer?: string | null }) {
  const assessment = data.marked && data.score && (
    <div className="space-y-3">
      <h3 className="sr-only">Assessment</h3>
      <p>
        <ScoreBadge score={data.score} />
      </p>
      {data.feedbackSummary && <p>{data.feedbackSummary}</p>}
      <List title="What you got right" items={data.correctElements ?? []} />
      <List title="Missing or wrong" items={data.missingOrWrong ?? []} />
      {data.sourceQuote && <blockquote className="border-l-4 border-highlight pl-3 text-sm italic">{data.sourceQuote}</blockquote>}
    </div>
  );
  const yours = answer ? (
    <div className="space-y-2 rounded-sm bg-surface-container p-4">
      <h3 className="text-xs font-medium uppercase tracking-widest text-on-surface-variant">Your answer</h3>
      <p className="whitespace-pre-wrap text-sm">{answer}</p>
    </div>
  ) : null;

  return (
    <section aria-label="Feedback" className="space-y-4">
      {yours ? (
        <div className="grid gap-4 md:grid-cols-2">
          {yours}
          {assessment || <Source data={data} />}
        </div>
      ) : (
        assessment
      )}
      {(assessment || !yours) && <Source data={data} />}
      <p className="text-xs text-on-surface-variant">
        {data.marked ? "AI marking can be wrong. " : ""}Study aid, not clinical guidance: check the current CMG before you
        rely on anything here.
      </p>
    </section>
  );
}

export function SelfGrade({
  value,
  onChoose,
  disabled,
}: {
  value: Score | null;
  onChoose: (score: Score) => void;
  disabled?: boolean;
}) {
  return (
    <fieldset className="space-y-2 rounded-sm bg-surface-container-low p-4">
      <legend className="text-sm font-semibold">How did you go?</legend>
      <div className="flex flex-wrap gap-2">
        {(["correct", "partial", "incorrect"] as const).map((score) => (
          <button
            key={score}
            type="button"
            aria-pressed={value === score}
            disabled={disabled}
            onClick={() => onChoose(score)}
            className={`min-h-11 rounded-sm px-4 py-2 text-sm font-semibold disabled:opacity-50 ${
              value === score ? SCORE_CLASS[score] : "bg-surface-container-high"
            }`}
          >
            {SELF_LABEL[score]}
          </button>
        ))}
      </div>
      {value && (
        <p role="status" className="text-xs text-on-surface-variant">
          Saved to your progress.
        </p>
      )}
    </fieldset>
  );
}
