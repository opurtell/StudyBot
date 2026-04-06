import type { EvaluateResponse } from "../types/api";
import MarkdownRenderer from "./MarkdownRenderer";

interface FeedbackSplitViewProps {
  userAnswer: string;
  evaluation: EvaluateResponse;
}

export default function FeedbackSplitView({ userAnswer, evaluation }: FeedbackSplitViewProps) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
      <div>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-headline text-headline-md text-primary">
            Your Answer
          </h3>
          <span className="font-mono text-[10px] text-on-surface-variant">
            ANSWER
          </span>
        </div>
        <div className="bg-surface-container-low p-8 min-h-[500px]">
          <p className="font-body text-body-md text-on-surface whitespace-pre-wrap">
            {userAnswer}
          </p>
        </div>
      </div>

      <div>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-headline text-headline-md text-primary">
            Evaluation
          </h3>
          {evaluation.score && (
            <span className="font-mono text-[10px] text-on-surface-variant">
              Score: {evaluation.score === "correct" ? "100" : evaluation.score === "partial" ? "50" : "0"}%
            </span>
          )}
        </div>
        <div className="bg-surface-container p-8 min-h-[500px] space-y-6">
          {evaluation.correct_elements.length > 0 && (
            <div className="border-l-4 border-primary pl-4">
              <p className="font-label text-label-sm text-on-surface-variant mb-2">
                Correct Elements
              </p>
              <ul className="space-y-1">
                {evaluation.correct_elements.map((el, i) => (
                  <li key={i} className="font-body text-body-md text-on-surface">
                    <MarkdownRenderer content={el} />
                  </li>
                ))}
              </ul>
            </div>
          )}

          {evaluation.missing_or_wrong.length > 0 && (
            <div className="border-l-4 border-error pl-4">
              <p className="font-label text-label-sm text-on-surface-variant mb-2">
                {evaluation.score === "incorrect"
                  ? "Incorrect Elements"
                  : "Missing or Incorrect"}
              </p>
              <ul className="space-y-1">
                {evaluation.missing_or_wrong.map((el, i) => {
                  const isCritical = evaluation.score === "incorrect";
                  return (
                    <li
                      key={i}
                      className={`font-body text-body-md flex items-start gap-2 ${
                        isCritical ? "text-rose-700" : "text-on-surface"
                      }`}
                    >
                      <span
                        className={`material-symbols-outlined text-sm mt-0.5 ${
                          isCritical ? "text-rose-700" : "text-status-critical"
                        }`}
                      >
                        {isCritical ? "warning" : "close"}
                      </span>
                      <MarkdownRenderer content={el} />
                    </li>
                  );
                })}
              </ul>
            </div>
          )}

          {evaluation.feedback_summary && (
            <MarkdownRenderer content={evaluation.feedback_summary} className="italic opacity-80" />
          )}

          <div className="pt-4 border-t border-outline-variant/10 space-y-1">
            <p className="font-label text-label-sm text-on-surface-variant">Source</p>
            <p className="font-mono text-[10px] text-on-surface">{evaluation.source_citation}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
