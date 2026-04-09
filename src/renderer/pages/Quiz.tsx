import { useState, useEffect, useRef } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useQuizSession } from "../hooks/useQuizSession";
import { useQuizShortcuts } from "../hooks/useQuizShortcuts";
import { useResourceCacheStore } from "../providers/ResourceCacheProvider";
import ProgressBar from "../components/ProgressBar";
import QuizQuestion from "../components/QuizQuestion";
import AnswerInput from "../components/AnswerInput";
import QuizTimer from "../components/QuizTimer";
import Button from "../components/Button";
import MarkdownRenderer from "../components/MarkdownRenderer";
import LoadingIndicator from "../components/LoadingIndicator";
import { QUIZ_CATEGORIES } from "../data/quizCategories";

interface GuidelineRevisionState {
  scope: "guideline" | "section" | "all";
  guidelineId: string | null;
  section: string | null;
}

interface QuizResumeState {
  action: "continue";
  sessionId: string;
  questionCount: number;
}

export default function Quiz() {
  const navigate = useNavigate();
  const location = useLocation();
  const session = useQuizSession();
  const cacheStore = useResourceCacheStore();
  const [answer, setAnswer] = useState("");
  const [timerRunning, setTimerRunning] = useState(false);
  const [randomize, setRandomize] = useState(true);
  const revisionLaunched = useRef(false);
  const resumeLaunched = useRef(false);

  useEffect(() => {
    if (resumeLaunched.current) return;
    const state = location.state as QuizResumeState | null;
    if (!state?.action || state.action !== "continue" || !state.sessionId) return;
    resumeLaunched.current = true;
    navigate(location.pathname, { replace: true, state: null });
    void session.resumeSession(state.sessionId, state.questionCount);
  }, [location.state]);

  useEffect(() => {
    if (revisionLaunched.current) return;
    const state = location.state as GuidelineRevisionState | null;
    if (!state?.scope || session.phase !== "idle") return;
    revisionLaunched.current = true;
    navigate(location.pathname, { replace: true, state: null });

    if (state.scope === "all") {
      session.startSession({ mode: "clinical_guidelines", randomize });
    } else if (state.section) {
      session.startSession({ mode: "topic", topic: state.section, randomize });
    }
  }, [location.state, session.phase]);

  useEffect(() => {
    if (session.phase === "question") {
      setAnswer("");
      setTimerRunning(true);
    } else {
      setTimerRunning(false);
    }
  }, [session.phase, session.questionCount]);

  // Invalidate dashboard cache after each evaluation so the Observations
  // tab shows fresh mastery and history data on the next visit.
  useEffect(() => {
    if (session.phase === "feedback") {
      cacheStore.invalidate("/quiz/dashboard-mastery");
      cacheStore.invalidate("/quiz/history?limit=3::3");
    }
  }, [session.phase, cacheStore]);

  const handleSubmit = () => {
    session.submitAnswer(answer || null);
  };

  const handleReveal = () => {
    session.submitAnswer(null);
  };

  const handleViewFullAnalysis = () => {
    if (!session.evaluation || !session.question) {
      return;
    }

    navigate("/feedback", {
      state: {
        questionText: session.question.question_text,
        userAnswer: answer,
        evaluation: session.evaluation,
        elapsedSeconds: session.elapsedSeconds,
        category: session.question.category,
        questionType: session.question.question_type,
        sessionId: session.sessionId,
        questionCount: session.questionCount,
      }
    });
  };

  const handleExit = () => {
    session.endSession();
    navigate("/");
  };

  useQuizShortcuts([
    {
      key: "1",
      enabled: session.phase === "idle",
      action: () => {
        void session.startSession({ mode: "random", randomize });
      },
    },
    {
      key: "2",
      enabled: session.phase === "idle",
      action: () => {
        void session.startSession({ mode: "gap_driven", randomize });
      },
    },
    {
      key: "3",
      enabled: session.phase === "idle",
      action: () => {
        void session.startSession({ mode: "clinical_guidelines", randomize });
      },
    },
    {
      key: "4",
      enabled: session.phase === "idle",
      action: () => {
        void session.startSession({ mode: "topic", topic: "Medicine", randomize });
      },
    },
    {
      key: "5",
      enabled: session.phase === "idle",
      action: () => {
        void session.startSession({ mode: "topic", topic: "Clinical Skill", randomize });
      },
    },
    {
      key: "6",
      enabled: session.phase === "idle",
      action: () => {
        void session.startSession({ mode: "topic", topic: "Pharmacology", randomize });
      },
    },
    {
      key: "7",
      enabled: session.phase === "idle",
      action: () => {
        void session.startSession({ mode: "topic", topic: "Pathophysiology", randomize });
      },
    },
    {
      key: "v",
      enabled: session.phase === "idle",
      action: () => setRandomize((current) => !current),
    },
    {
      key: "Escape",
      enabled: session.phase === "idle" || session.phase === "question" || session.phase === "feedback" || session.phase === "error",
      allowInEditable: true,
      action: handleExit,
    },
    {
      key: "Enter",
      meta: true,
      enabled: session.phase === "question",
      allowInEditable: true,
      action: () => {
        void handleSubmit();
      },
    },
    {
      key: "r",
      meta: true,
      shift: true,
      enabled: session.phase === "question",
      action: () => {
        void handleReveal();
      },
    },
    {
      key: "a",
      meta: true,
      shift: true,
      enabled: session.phase === "feedback",
      action: handleViewFullAnalysis,
    },
    {
      key: "ArrowRight",
      meta: true,
      enabled: session.phase === "feedback",
      action: () => {
        void session.nextQuestion();
      },
    },
  ]);

  if (session.phase === "idle") {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center px-8">
        <div className="max-w-xl text-center space-y-8">
          <span className="inline-block bg-tertiary-fixed/40 px-3 py-1 font-label text-[10px] uppercase tracking-widest text-on-surface-variant">
            Active Recall
          </span>
          <h1 className="font-headline text-display-sm text-primary">
            Start Quiz
          </h1>
          <p className="font-body text-body-md text-on-surface-variant">
            Select a session mode to begin active recall quizzing.
          </p>
          {!session.backendReady && (
            <p className="font-mono text-[10px] text-on-surface-variant">
              Quiz actions are paused until the backend returns.
            </p>
          )}

          <div className="space-y-3">
            <div className="space-y-1">
              <span className="font-label text-[10px] text-on-surface-variant uppercase tracking-widest">
                Session Variety Mode
              </span>
              <p className="font-mono text-[10px] text-on-surface-variant/80">
                `V` toggles variety mode
              </p>
            </div>
            <div className="flex gap-2 justify-center">
              <button
                onClick={() => setRandomize(true)}
                aria-keyshortcuts="V"
                className={`px-4 py-2 font-label text-[10px] uppercase tracking-wider transition-colors border border-outline-variant/20 ${
                  randomize ? "bg-primary text-on-primary border-primary" : "bg-surface-container-high text-on-surface-variant hover:bg-surface-container-highest"
                }`}
              >
                Maximum Variety
              </button>
              <button
                onClick={() => setRandomize(false)}
                className={`px-4 py-2 font-label text-[10px] uppercase tracking-wider transition-colors border border-outline-variant/20 ${
                  !randomize ? "bg-primary text-on-primary border-primary" : "bg-surface-container-high text-on-surface-variant hover:bg-surface-container-highest"
                }`}
              >
                Strict Relevance
              </button>
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3 max-w-3xl mx-auto pt-4">
            <Button
              onClick={() => session.startSession({ mode: "random", randomize })}
              aria-keyshortcuts="1"
              disabled={!session.backendReady}
              className="w-full justify-center"
            >
              Random
              <span className="font-mono text-[10px] normal-case tracking-normal opacity-80">1</span>
            </Button>
            <Button
              onClick={() => session.startSession({ mode: "gap_driven", randomize })}
              variant="secondary"
              aria-keyshortcuts="2"
              disabled={!session.backendReady}
              className="w-full justify-center"
            >
              Gap-Driven
              <span className="font-mono text-[10px] normal-case tracking-normal opacity-80">2</span>
            </Button>
            <Button
              onClick={() => session.startSession({ mode: "clinical_guidelines", randomize })}
              variant="secondary"
              aria-keyshortcuts="3"
              disabled={!session.backendReady}
              className="w-full justify-center"
            >
              Clinical Guidelines
              <span className="font-mono text-[10px] normal-case tracking-normal opacity-80">3</span>
            </Button>
            <Button
              onClick={() => session.startSession({ mode: "topic", topic: "Medicine", randomize })}
              variant="secondary"
              aria-keyshortcuts="4"
              disabled={!session.backendReady}
              className="w-full justify-center"
            >
              Medication Guidelines
              <span className="font-mono text-[10px] normal-case tracking-normal opacity-80">4</span>
            </Button>
            <Button
              onClick={() => session.startSession({ mode: "topic", topic: "Clinical Skill", randomize })}
              variant="secondary"
              aria-keyshortcuts="5"
              disabled={!session.backendReady}
              className="w-full justify-center"
            >
              Clinical Skills
              <span className="font-mono text-[10px] normal-case tracking-normal opacity-80">5</span>
            </Button>
            <Button
              onClick={() => session.startSession({ mode: "topic", topic: "Pharmacology", randomize })}
              variant="secondary"
              aria-keyshortcuts="6"
              disabled={!session.backendReady}
              className="w-full justify-center"
            >
              Pharmacology
              <span className="font-mono text-[10px] normal-case tracking-normal opacity-80">6</span>
            </Button>
            <Button
              onClick={() => session.startSession({ mode: "topic", topic: "Pathophysiology", randomize })}
              variant="secondary"
              aria-keyshortcuts="7"
              disabled={!session.backendReady}
              className="w-full justify-center"
            >
              Pathophysiology
              <span className="font-mono text-[10px] normal-case tracking-normal opacity-80">7</span>
            </Button>
          </div>

          <div className="pt-8">
            <span className="font-label text-[10px] text-on-surface-variant uppercase tracking-widest">
              Focus Sessions
            </span>
            <div className="grid grid-cols-3 gap-2 pt-3 max-w-sm mx-auto">
              {QUIZ_CATEGORIES.map((cat) => (
                <button
                  key={cat.section}
                  onClick={() => session.startSession({ mode: "topic", topic: cat.section, randomize })}
                  disabled={!session.backendReady}
                  className="px-3 py-2 font-label text-[10px] uppercase tracking-wider transition-colors border border-outline-variant/20 bg-surface-container-high text-on-surface-variant hover:bg-surface-container-highest hover:text-primary"
                >
                  {cat.display}
                </button>
              ))}
            </div>
          </div>

          <div className="pt-6 max-w-xs mx-auto">
            <Button onClick={handleExit} variant="tertiary" aria-keyshortcuts="Escape">
              Return to Dashboard
              <span className="font-mono text-[10px] normal-case tracking-normal opacity-80">Esc</span>
            </Button>
          </div>
        </div>
      </div>
    );
  }

  if (session.phase === "error") {
    const isRateLimit =
      session.error?.toLowerCase().includes("quota") ||
      session.error?.toLowerCase().includes("429") ||
      session.error?.toLowerCase().includes("rate limit") ||
      session.error?.toLowerCase().includes("resource exhausted") ||
      session.error?.toLowerCase().includes("too many requests");

    return (
      <div className="min-h-screen flex flex-col items-center justify-center px-8">
        <div className="max-w-md text-center space-y-6">
          {isRateLimit ? (
            <>
              <span className="inline-block bg-amber-500/20 px-3 py-1 font-label text-[10px] uppercase tracking-widest text-amber-600">
                Quota Exceeded
              </span>
              <h2 className="font-headline text-headline-md text-primary">
                LLM Rate Limit Reached
              </h2>
              <p className="font-body text-body-md text-on-surface-variant">
                The configured LLM provider has exhausted its request quota. Wait a moment and try again, or switch to a different provider in Settings.
              </p>
            </>
          ) : (
            <>
              <span className="inline-block bg-rose-500/20 px-3 py-1 font-label text-[10px] uppercase tracking-widest text-status-critical">
                Error
              </span>
              <p className="font-mono text-[11px] text-on-surface-variant break-words">
                {session.error}
              </p>
            </>
          )}
          <Button onClick={handleExit} variant="tertiary" aria-keyshortcuts="Escape">
            Return to Dashboard
            <span className="font-mono text-[10px] normal-case tracking-normal opacity-80">Esc</span>
          </Button>
        </div>
      </div>
    );
  }

  if (session.phase === "loading") {
    return (
      <div className="min-h-screen flex flex-col">
        <ProgressBar percent={(session.questionCount / 10) * 100} />
        <div className="flex-1 flex items-center justify-center">
          <div className="space-y-3 text-center">
            <LoadingIndicator type="generation" />
            <p className="font-mono text-[10px] text-on-surface-variant">
              {session.loadingLabel ?? "Generating question..."}
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (session.phase === "feedback" && session.evaluation && session.question) {
    const eval_ = session.evaluation;
    const q = session.question;

    return (
      <div className="min-h-screen flex flex-col">
        <ProgressBar percent={(session.questionCount / 10) * 100} />
        <div className="flex-1 px-8 py-12 max-w-3xl mx-auto w-full">
          <div className="mb-8">
            <span className="font-mono text-[10px] text-on-surface-variant">
              Question {session.questionCount} — {q.category}
            </span>
          </div>
          <div className="space-y-8">
            <div>
              <h2 className="font-headline text-headline-md text-primary mb-4">{q.question_text}</h2>
              {eval_.score && (
                <span className={`inline-block px-2 py-1 font-label text-label-sm uppercase ${
                  eval_.score === "correct" ? "bg-emerald-500/20 text-emerald-700" :
                  eval_.score === "partial" ? "bg-amber-400/20 text-amber-700" :
                  "bg-rose-300/20 text-rose-700"
                }`}>
                  {eval_.score}
                </span>
              )}
            </div>

            <div className="bg-surface-container-lowest border-l-2 border-tertiary-fixed p-6">
              <p className="font-label text-label-sm text-on-surface-variant mb-2">
                From the Source
              </p>
              <MarkdownRenderer content={eval_.source_quote} className="italic" />
              <p className="font-mono text-[10px] text-on-surface-variant mt-3">
                {eval_.source_citation}
              </p>
            </div>

            <p className="font-mono text-[10px] text-on-surface-variant/50">
              Model: {eval_.model_id}
            </p>

            {eval_.correct_elements.length > 0 && (
              <div>
                <p className="font-label text-label-sm text-on-surface-variant mb-2">Correct Elements</p>
                <ul className="space-y-1">
                  {eval_.correct_elements.map((el, i) => (
                    <li key={i} className="font-body text-body-md text-on-surface flex items-start gap-2">
                      <span className="text-emerald-500 mt-0.5 material-symbols-outlined text-sm">check</span>
                      <MarkdownRenderer content={el} />
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {eval_.missing_or_wrong.length > 0 && (
              <div>
                <p className="font-label text-label-sm text-on-surface-variant mb-2">Missing or Incorrect</p>
                <ul className="space-y-1">
                  {eval_.missing_or_wrong.map((el, i) => (
                    <li key={i} className="font-body text-body-md text-on-surface flex items-start gap-2">
                      <span className="text-status-critical mt-0.5 material-symbols-outlined text-sm">close</span>
                      <MarkdownRenderer content={el} />
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {eval_.feedback_summary && (
              <MarkdownRenderer content={eval_.feedback_summary} className="opacity-80" />
            )}
          </div>

          <div className="flex items-center gap-4 mt-12">
            <Button
              onClick={handleViewFullAnalysis}
              variant="secondary"
              aria-keyshortcuts="Meta+Shift+A Control+Shift+A"
            >
              View Full Analysis
              <span className="font-mono text-[10px] normal-case tracking-normal opacity-80">⌘/Ctrl+Shift+A</span>
            </Button>
            <Button
              onClick={() => session.nextQuestion()}
              aria-keyshortcuts="Meta+ArrowRight Control+ArrowRight"
            >
              Next Question
              <span className="material-symbols-outlined text-sm">arrow_forward</span>
              <span className="font-mono text-[10px] normal-case tracking-normal opacity-80">⌘/Ctrl+→</span>
            </Button>
            <Button onClick={handleExit} variant="tertiary" aria-keyshortcuts="Escape">
              End Session
              <span className="font-mono text-[10px] normal-case tracking-normal opacity-80">Esc</span>
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col">
      <ProgressBar percent={(session.questionCount / 10) * 100} />
      <div className="flex-1 px-8 py-12 max-w-3xl mx-auto w-full flex flex-col">
        <div className="flex items-center justify-between mb-8">
          <span className="font-mono text-[10px] text-on-surface-variant">
            Session {session.sessionId?.slice(-4)}
          </span>
          <QuizTimer running={timerRunning} onTick={session.setElapsedSeconds} />
        </div>

        {session.question && (
          <QuizQuestion
            questionNumber={session.questionCount}
            text={session.question.question_text}
            category={session.question.category}
          />
        )}

        {session.phase === "submitting" ? (
          <div className="flex-1 flex items-center justify-center mt-12">
            <div className="space-y-3 text-center">
              <LoadingIndicator type="evaluation" />
              <p className="font-mono text-[10px] text-on-surface-variant">
                {session.loadingLabel ?? "Evaluating answer..."}
              </p>
            </div>
          </div>
        ) : (
          <>
            <div className="flex-1 mt-12">
              <AnswerInput
                value={answer}
                onChange={setAnswer}
                onSubmit={handleSubmit}
                disabled={false}
              />
            </div>

            <div className="flex items-center justify-between mt-8">
              <button
                onClick={handleReveal}
                aria-keyshortcuts="Meta+Shift+R Control+Shift+R"
                className="flex items-center gap-2 text-on-surface-variant hover:text-primary transition-colors font-label text-sm uppercase tracking-wider"
              >
                <span className="material-symbols-outlined text-sm">help_outline</span>
                Reveal Reference
                <span className="font-mono text-[10px] normal-case tracking-normal opacity-80">⌘/Ctrl+Shift+R</span>
              </button>
              <div className="flex items-center gap-3">
                <Button onClick={handleExit} variant="tertiary" aria-keyshortcuts="Escape">
                  Skip
                  <span className="font-mono text-[10px] normal-case tracking-normal opacity-80">Esc</span>
                </Button>
                <Button
                  onClick={handleSubmit}
                  disabled={false}
                  aria-keyshortcuts="Enter Meta+Enter Control+Enter"
                >
                  Submit Answer
                  <span className="material-symbols-outlined text-sm">arrow_forward</span>
                  <span className="font-mono text-[10px] normal-case tracking-normal opacity-80">Enter / ⌘/Ctrl+Enter</span>
                </Button>
              </div>
            </div>
          </>
        )}

        <div className="flex items-center justify-between mt-12 pt-4 border-t border-outline-variant/10">
          <span className="font-mono text-[10px] text-on-surface-variant">
            Question {session.questionCount}
          </span>
        </div>
      </div>
    </div>
  );
}
