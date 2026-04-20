import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import type { FeedbackNavigationState } from "../types/api";
import { apiPost, getApiErrorMessage } from "../lib/apiClient";
import { useQuizShortcuts } from "../hooks/useQuizShortcuts";
import FeedbackSplitView from "../components/FeedbackSplitView";
import GroundTruth from "../components/GroundTruth";
import ResponseTimeMetrics from "../components/ResponseTimeMetrics";
import Button from "../components/Button";
import SourceFootnotes from "../components/SourceFootnotes";
import { ServiceChip } from "../components/ServiceChip";

type Score = "correct" | "partial" | "incorrect";

function getCorrectionOptions(modelScore: Score | null): Score[] {
  if (modelScore === "correct") return ["incorrect"];
  if (modelScore === "partial") return ["correct", "incorrect"];
  if (modelScore === "incorrect") return ["correct"];
  // null = reveal reference — user can pick any score
  return ["correct", "partial", "incorrect"];
}

const SCORE_LABELS: Record<Score, string> = {
  correct: "I was Correct",
  partial: "I was Partially Correct",
  incorrect: "I was Incorrect",
};

export default function Feedback() {
  const location = useLocation();
  const navigate = useNavigate();
  const state = location.state as FeedbackNavigationState | null;

  const [correcting, setCorrecting] = useState(false);
  const [correctedTo, setCorrectedTo] = useState<Score | null>(null);
  const [correctionError, setCorrectionError] = useState<string | null>(null);

  useQuizShortcuts([
    {
      key: "Escape",
      action: () => navigate("/"),
      allowInEditable: true,
    },
    {
      key: "Enter",
      allowInEditable: true,
      action: () => {
        if (state?.sessionId) {
          navigate("/quiz", { state: { action: "continue" as const, sessionId: state.sessionId, questionCount: state.questionCount } });
        } else {
          navigate("/");
        }
      },
    },
  ]);

  if (!state?.evaluation) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center px-8">
        <h2 className="font-headline text-headline-md text-on-surface-variant">
          No evaluation data available
        </h2>
        <Button
          onClick={() => navigate("/")}
          variant="tertiary"
          className="mt-4"
          aria-keyshortcuts="Escape Meta+ArrowRight Control+ArrowRight"
        >
          Return to Dashboard
          <span className="font-mono text-[10px] normal-case tracking-normal opacity-80">Esc</span>
        </Button>
      </div>
    );
  }

  const modelScore = state.evaluation.score as Score | null;
  const correctionOptions = getCorrectionOptions(modelScore);

  async function handleCorrect(newScore: Score) {
    if (!state?.questionId) return;
    setCorrecting(true);
    setCorrectionError(null);
    try {
      await apiPost("/quiz/question/correct", {
        question_id: state.questionId,
        corrected_score: newScore,
      });
      setCorrectedTo(newScore);
    } catch (err) {
      setCorrectionError(getApiErrorMessage(err, "Correction failed"));
    } finally {
      setCorrecting(false);
    }
  }

  return (
    <div className="min-h-screen">
      <div className="px-8 py-12 max-w-7xl mx-auto">
        <div className="border-l-4 border-primary pl-8 py-2 mb-8">
          <div className="mb-2">
            <ServiceChip />
          </div>
          <span className="font-mono text-[10px] text-on-surface-variant">
            Quiz Review
          </span>
          <h2 className="font-headline text-display-lg text-primary italic">
            Answer Feedback
          </h2>
        </div>

        <GroundTruth
          quote={state.evaluation.source_quote}
          citation={state.evaluation.source_citation}
        />

        <ResponseTimeMetrics elapsedSeconds={state.elapsedSeconds} />

        <div className="mt-8">
          <FeedbackSplitView
            userAnswer={state.userAnswer}
            evaluation={state.evaluation}
          />
        </div>

        <div className="mt-6">
          <SourceFootnotes citations={[state.evaluation.source_citation]} />
          <p className="font-mono text-[10px] text-on-surface-variant/50 mt-3">
            Model: {state.evaluation.model_id}
          </p>
        </div>

        {/* User correction section */}
        <div className="mt-6">
          {correctedTo ? (
            <p className="font-mono text-[10px] text-primary">
              Score corrected to: {correctedTo}
            </p>
          ) : (
            <>
              <p className="font-mono text-[10px] text-on-surface-variant mb-2">
                Model scored: {modelScore ?? "self-graded"}
              </p>
              <div className="flex items-center gap-3">
                {correctionOptions.map((opt) => (
                  <Button
                    key={opt}
                    onClick={() => handleCorrect(opt)}
                    variant="tertiary"
                    disabled={correcting}
                  >
                    {SCORE_LABELS[opt]}
                  </Button>
                ))}
              </div>
              {correctionError && (
                <p className="font-mono text-[10px] text-error mt-2">
                  {correctionError}
                </p>
              )}
            </>
          )}
        </div>

        <div className="mt-8 flex items-center gap-4">
          <Button
            onClick={() => navigate("/")}
            variant="secondary"
            aria-keyshortcuts="Escape"
          >
            Return to Dashboard
            <span className="font-mono text-[10px] normal-case tracking-normal opacity-80">Esc</span>
          </Button>
          {state?.sessionId && (
            <Button
              onClick={() =>
                navigate("/quiz", {
                  state: { action: "continue" as const, sessionId: state.sessionId, questionCount: state.questionCount },
                })
              }
              aria-keyshortcuts="Enter"
            >
              Continue Quiz
              <span className="material-symbols-outlined text-sm">arrow_forward</span>
              <span className="font-mono text-[10px] normal-case tracking-normal opacity-80">Enter</span>
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
