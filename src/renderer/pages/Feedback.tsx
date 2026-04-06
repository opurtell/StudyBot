import { useLocation, useNavigate } from "react-router-dom";
import type { FeedbackNavigationState } from "../types/api";
import { useQuizShortcuts } from "../hooks/useQuizShortcuts";
import FeedbackSplitView from "../components/FeedbackSplitView";
import GroundTruth from "../components/GroundTruth";
import ResponseTimeMetrics from "../components/ResponseTimeMetrics";
import Button from "../components/Button";
import SourceFootnotes from "../components/SourceFootnotes";

export default function Feedback() {
  const location = useLocation();
  const navigate = useNavigate();
  const state = location.state as FeedbackNavigationState | null;

  useQuizShortcuts([
    {
      key: "Escape",
      action: () => navigate("/"),
      allowInEditable: true,
    },
    {
      key: "ArrowRight",
      meta: true,
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

  return (
    <div className="min-h-screen">
      <div className="px-8 py-12 max-w-7xl mx-auto">
        <div className="border-l-4 border-primary pl-8 py-2 mb-8">
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
              aria-keyshortcuts="Meta+ArrowRight Control+ArrowRight"
            >
              Continue Quiz
              <span className="material-symbols-outlined text-sm">arrow_forward</span>
              <span className="font-mono text-[10px] normal-case tracking-normal opacity-80">⌘/Ctrl+→</span>
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
