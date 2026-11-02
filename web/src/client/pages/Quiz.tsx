import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { Link, useSearchParams } from "react-router";
import { documentPath } from "../components/Feedback";
import { useFocusMode } from "../components/Layout";
import { correctionOptions, Kbd, MarkPanel, QuizTimer, ReportDialog, SCORES, SelfMark, ShortcutHelp, SourcePanel } from "../components/QuizParts";
import { ScopePicker } from "../components/ScopePicker";
import { TopicPicker } from "../components/TopicPicker";
import {
  api,
  ApiError,
  type Difficulty,
  type Mark,
  type Quota,
  type QuizFilters,
  type QuizQuestion,
  type Reveal,
  type Score,
  type Topic,
} from "../lib/api";
import { gradeGuestAttempt, recordGuestAttempt } from "../lib/guestProgress";
import { usePreferences } from "../lib/preferences";
import { buildGroups, EVERYTHING, poolsLabel, resolveSelection, selectionFromLink, type Selection } from "../lib/quizSelection";
import { QUIZ_SCOPE_OPTIONS, quizScopeName, useQuizScope, viewFor } from "../lib/scopeView";
import { useSession } from "../lib/session";
import { useShortcuts } from "../lib/useShortcuts";

const SEEN_KEY = "quiz-seen";
const MAX_SEEN = 400;

const DIFFICULTIES: { value: Difficulty | ""; label: string }[] = [
  { value: "", label: "Any" },
  { value: "easy", label: "Easy" },
  { value: "medium", label: "Medium" },
  { value: "hard", label: "Hard" },
];

function loadSeen(): string[] {
  try {
    const raw = JSON.parse(localStorage.getItem(SEEN_KEY) ?? "[]") as unknown;
    return Array.isArray(raw) ? raw.filter((id): id is string => typeof id === "string").slice(-MAX_SEEN) : [];
  } catch {
    return [];
  }
}

function rememberSeen(id: string) {
  try {
    const seen = loadSeen().filter((s) => s !== id);
    seen.push(id);
    localStorage.setItem(SEEN_KEY, JSON.stringify(seen.slice(-MAX_SEEN)));
  } catch {
    return;
  }
}

function message(err: unknown): string {
  return err instanceof Error ? err.message : "Something went wrong. Try again shortly.";
}

export function Quiz() {
  const { me, refresh } = useSession();
  const signedIn = Boolean(me?.signedIn);
  const [choice, setChoice] = useQuizScope();
  const { prefs } = usePreferences();
  const view = viewFor(choice);
  const icpOnly = choice.level === "icp_only";
  const [params] = useSearchParams();
  const linkDocument = params.get("document");
  const linkSection = linkDocument ? null : params.get("section");
  const [selection, setSelection] = useState<Selection>(EVERYTHING);
  const [linkApplied, setLinkApplied] = useState(!linkDocument && !linkSection);
  const [pickerOpen, setPickerOpen] = useState(true);
  const [difficulty, setDifficulty] = useState<Difficulty | "">("");
  const [topics, setTopics] = useState<{ view: string; current: Topic[]; all: Topic[] } | null>(null);
  const topicsKey = `${view}:${icpOnly ? "icp_only" : "all"}`;
  const [topicsError, setTopicsError] = useState<string | null>(null);

  const [question, setQuestion] = useState<QuizQuestion | null>(null);
  const [questionView, setQuestionView] = useState(view);
  const [exhausted, setExhausted] = useState(false);
  const [canGenerate, setCanGenerate] = useState(false);
  const [quota, setQuota] = useState<Quota | null>(null);
  const [answer, setAnswer] = useState("");
  const [result, setResult] = useState<Mark | Reveal | null>(null);
  const [submitted, setSubmitted] = useState("");
  const [selfScore, setSelfScore] = useState<Score | null>(null);
  const guestAttempt = useRef<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const started = useRef(Date.now());
  const [startedAt, setStartedAt] = useState(() => Date.now());
  const [stoppedAt, setStoppedAt] = useState<number | null>(null);
  const [corrected, setCorrected] = useState<Score | null>(null);
  const [reportOpen, setReportOpen] = useState(false);
  const [reported, setReported] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [tab, setTab] = useState<"marking" | "source">("marking");
  const [count, setCount] = useState(0);
  const closeReport = useCallback(() => setReportOpen(false), []);
  const closeHelp = useCallback(() => setHelpOpen(false), []);
  const answerBox = useRef<HTMLTextAreaElement>(null);
  const nextButton = useRef<HTMLButtonElement>(null);
  useFocusMode(!pickerOpen);

  useEffect(() => {
    let live = true;
    setTopicsError(null);
    Promise.all([api.topics(view, icpOnly), view === "icp_pacer" && !icpOnly ? null : api.topics("icp_pacer")])
      .then(([current, all]) => {
        if (live) setTopics({ view: topicsKey, current: current.topics, all: (all ?? current).topics });
      })
      .catch(() => {
        if (live) setTopicsError("Couldn't load the topic list.");
      });
    return () => {
      live = false;
    };
  }, [view, icpOnly, topicsKey]);

  const groups = useMemo(() => (topics?.view === topicsKey ? buildGroups(topics.current) : []), [topics, topicsKey]);
  const allGroups = useMemo(() => (topics ? buildGroups(topics.all) : []), [topics]);

  useEffect(() => {
    if (linkApplied || groups.length === 0) return;
    const linked = selectionFromLink(groups, { document: linkDocument, section: linkSection });
    if (linked) setSelection(linked);
    setLinkApplied(true);
  }, [groups, linkApplied, linkDocument, linkSection]);

  useEffect(() => {
    if (me?.signedIn) setQuota(me.quota);
  }, [me]);

  const resolved = resolveSelection(selection, groups, prefs);
  const legacyLink = !linkApplied;
  const filters: QuizFilters = legacyLink
    ? {
        view,
        icpOnly,
        documentId: linkDocument,
        section: linkSection,
        difficulty: difficulty || null,
        excludedSections: prefs.excludedSections,
        excludedDocuments: prefs.excludedDocuments,
      }
    : {
        view,
        icpOnly,
        difficulty: difficulty || null,
        ...resolved.filters,
        excludedSections: resolved.useSettings ? prefs.excludedSections : [],
        excludedDocuments: resolved.useSettings ? prefs.excludedDocuments : [],
      };
  const scopeLabel = quizScopeName(choice);
  const difficultyLabel = DIFFICULTIES.find((d) => d.value === difficulty)?.label ?? "Any";
  const pickCount = resolved.picked.length;

  const choose = (next: Selection) => {
    setSelection(next);
    setLinkApplied(true);
  };

  function show(next: QuizQuestion | null) {
    setQuestion(next);
    setQuestionView(view);
    setAnswer("");
    setResult(null);
    setSubmitted("");
    setSelfScore(null);
    guestAttempt.current = null;
    started.current = Date.now();
    setStartedAt(started.current);
    setStoppedAt(null);
    setCorrected(null);
    setReportOpen(false);
    setReported(false);
    setMenuOpen(false);
    setTab("marking");
    if (next) setCount((c) => c + 1);
    if (next && !signedIn) rememberSeen(next.id);
  }

  async function run(label: string, fn: () => Promise<void>) {
    setBusy(label);
    setError(null);
    try {
      await fn();
    } catch (err) {
      setError(message(err));
    } finally {
      setBusy(null);
    }
  }

  const nextQuestion = (repeat = false) =>
    run("next", async () => {
      setPickerOpen(false);
      const res = await api.nextQuestion(filters, signedIn ? [] : loadSeen(), repeat);
      show(res.question);
      setExhausted(res.exhausted);
      setCanGenerate(res.canGenerate);
      if (res.quota) setQuota(res.quota);
    });

  const generate = () =>
    run("generate", async () => {
      const res = await api.generateQuestion(filters);
      show(res.question);
      setExhausted(false);
      setQuota(res.quota);
      void refresh();
    });

  const reveal = () =>
    run("reveal", async () => {
      if (!question) return;
      const typed = answer.trim();
      const res = await api.reveal(question.id, questionView, typed);
      setSubmitted(typed);
      setResult(res);
      setStoppedAt(Date.now());
      if (!signedIn) {
        guestAttempt.current = recordGuestAttempt({
          questionId: question.id,
          questionText: question.text,
          documentId: question.documentId,
          documentTitle: question.documentTitle,
          section: res.section ?? question.section ?? "Other",
          score: null,
        });
      }
    });

  const grade = (score: Score) =>
    run("grade", async () => {
      if (signedIn) {
        if (!result?.attemptId) return;
        await api.selfGrade(result.attemptId, score);
      } else if (guestAttempt.current) {
        gradeGuestAttempt(guestAttempt.current, score);
      }
      setSelfScore(score);
    });

  const correct = (score: Score) =>
    run("grade", async () => {
      if (!result?.attemptId) return;
      await api.selfGrade(result.attemptId, score);
      setCorrected(score);
    });

  const mark = (e?: FormEvent) => {
    e?.preventDefault();
    return run("mark", async () => {
      if (!question) return;
      try {
        const res = await api.mark(question.id, questionView, answer, Date.now() - started.current);
        setSubmitted(answer.trim());
        setResult(res);
        setStoppedAt(Date.now());
        setQuota(res.quota);
        void refresh();
      } catch (err) {
        if (err instanceof ApiError && err.code === "quota_exhausted") void refresh();
        throw err;
      }
    });
  };

  const marksLeft = quota?.marking.remaining ?? 0;
  const marked = result && "correctElements" in result ? result : null;
  const answered = result !== null;
  const canSelfMark = result !== null && !marked && (signedIn ? Boolean(result.attemptId) : true);
  const canCorrect = (score: Score) => Boolean(marked && signedIn && marked.attemptId && !corrected && correctionOptions(marked.score).includes(score));
  const dialogOpen = reportOpen || helpOpen;
  const inQuiz = !pickerOpen;
  const answering = inQuiz && question !== null && !answered;
  const startDisabled = busy !== null || (linkApplied && groups.length > 0 && resolved.inPlay.length === 0);
  const pickLabel = pickCount > 0 ? `${pickCount} ${selection.mode === "only" ? "picked" : "left out"}` : "";

  function end() {
    show(null);
    setExhausted(false);
    setError(null);
    setHelpOpen(false);
    setCount(0);
    setPickerOpen(true);
  }

  function openGuideline() {
    if (!question) return;
    window.open(documentPath(result?.documentId ?? question.documentId), "_blank", "noopener");
  }

  function submit() {
    if (busy !== null || !question) return;
    if (signedIn && answer.trim() && marksLeft > 0) void mark();
    else void reveal();
  }

  function onAnswerKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key !== "Enter" || e.shiftKey || e.nativeEvent.isComposing) return;
    if (!window.matchMedia?.("(pointer: fine)").matches) return;
    e.preventDefault();
    submit();
  }

  useEffect(() => {
    if (question && !result && window.matchMedia?.("(pointer: fine)").matches) answerBox.current?.focus({ preventScroll: true });
  }, [question, result]);

  useEffect(() => {
    if (result) nextButton.current?.focus({ preventScroll: true });
  }, [result]);

  useShortcuts([
    {
      key: "Escape",
      enabled: inQuiz && !dialogOpen,
      allowInEditable: true,
      action: () => (menuOpen ? setMenuOpen(false) : end()),
    },
    { key: "?", enabled: inQuiz && !dialogOpen, action: () => setHelpOpen(true) },
    { key: "r", alt: true, enabled: answering && busy === null && !dialogOpen, allowInEditable: true, action: () => void reveal() },
    { key: "s", alt: true, enabled: answering && busy === null && !dialogOpen, allowInEditable: true, action: () => void nextQuestion() },
    { key: "Enter", enabled: inQuiz && answered && busy === null && !dialogOpen, action: () => void nextQuestion() },
    {
      key: "Enter",
      enabled: inQuiz && exhausted && !question && busy === null && !dialogOpen,
      action: () => (canGenerate && quota ? void generate() : void nextQuestion(true)),
    },
    { key: "Enter", enabled: pickerOpen && !startDisabled, action: () => void nextQuestion() },
    { key: "g", enabled: inQuiz && answered && !dialogOpen, action: openGuideline },
    { key: "f", enabled: inQuiz && answered && !reported && !dialogOpen, action: () => setReportOpen(true) },
    ...SCORES.map((score, i) => ({
      key: String(i + 1),
      enabled: inQuiz && !dialogOpen && busy === null && (canSelfMark || canCorrect(score)),
      action: () => (canSelfMark ? void grade(score) : void correct(score)),
    })),
  ]);

  if (pickerOpen) {
    return (
      <div className="space-y-6">
        <header className="space-y-2">
          <h1 className="font-headline text-3xl font-semibold">Quiz</h1>
          <p className="text-on-surface-variant">
            Questions come from the ACTAS guidelines. Answer from memory, then check against the source.
          </p>
        </header>
        {error && (
          <p role="alert" className="rounded-sm bg-error-container p-3 text-sm text-error">
            {error}
          </p>
        )}
        <TopicPicker
          groups={groups}
          allGroups={allGroups}
          loading={!topics && !topicsError}
          error={topicsError}
          selection={selection}
          onChange={choose}
          prefs={prefs}
          scopeName={scopeLabel}
          details={[
            { label: "Scope", value: scopeLabel },
            { label: "Difficulty", value: difficultyLabel },
          ]}
          controls={
            <section aria-label="Quiz settings" className="flex flex-col gap-3 rounded-sm bg-surface-container-low p-3 sm:flex-row sm:flex-wrap sm:items-center sm:gap-x-8">
              <ScopePicker level={choice.level} pacer={choice.pacer} options={QUIZ_SCOPE_OPTIONS} onChange={setChoice} legend="Questions for" label="Scope" />
              {icpOnly && <p className="px-3 text-sm text-on-surface-variant sm:px-0">Only questions on ICP-specific content, without the AP material.</p>}
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-3 sm:px-0">
                <span className="text-xs font-medium uppercase tracking-widest text-on-surface-variant" aria-hidden="true">
                  Difficulty
                </span>
                <div className="flex gap-1" role="radiogroup" aria-label="Difficulty">
                  {DIFFICULTIES.map((d) => (
                    <button
                      key={d.label}
                      type="button"
                      role="radio"
                      aria-checked={difficulty === d.value}
                      onClick={() => setDifficulty(d.value)}
                      className={`min-h-10 rounded-sm px-3 py-2 text-sm font-medium ${difficulty === d.value ? "bg-primary text-on-primary" : "hover:bg-surface-container"}`}
                    >
                      {d.label}
                    </button>
                  ))}
                </div>
              </div>
            </section>
          }
          start={{
            resolved,
            button: (
              <button
                type="button"
                onClick={() => void nextQuestion()}
                disabled={startDisabled}
                aria-keyshortcuts="Enter"
                className="min-h-12 w-full rounded-sm bg-primary px-5 text-base font-semibold text-on-primary disabled:opacity-50"
              >
                {busy === "next" ? "Finding a question…" : "Start"}
              </button>
            ),
          }}
        />
      </div>
    );
  }

  const sidePhone = marked ? (tab === "marking" ? "flex [grid-area:work]" : "hidden") : canSelfMark ? "flex [grid-area:side]" : "hidden";
  const workPhone = marked && tab === "marking" ? "hidden" : "flex";
  const disclaimer = (
    <p className="text-xs text-on-surface-variant">
      {marked ? "AI marking can be wrong. " : ""}Study aid, not clinical guidance: check the current CMG before you rely on anything here.
    </p>
  );

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <h1 className="sr-only">Quiz</h1>

      <div className="relative flex flex-none items-center gap-1 bg-surface-container-low px-2 pt-[calc(0.5rem+env(safe-area-inset-top))] pb-2 lg:hidden">
        <button type="button" aria-label="End session" onClick={end} className="inline-flex size-11 items-center justify-center rounded-sm hover:bg-surface-container">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <path d="M6 6l12 12M18 6L6 18" />
          </svg>
        </button>
        <div className="min-w-0 flex-1 text-center">
          <p className="truncate font-headline text-lg font-semibold text-primary">
            {poolsLabel(selection)}
            {pickLabel && ` · ${pickLabel}`}
          </p>
          <p className="font-mono text-xs text-on-surface-variant">
            {question && (
              <>
                Q{count} · <QuizTimer startedAt={startedAt} stoppedAt={stoppedAt} /> ·{" "}
              </>
            )}
            {scopeLabel}
          </p>
        </div>
        <button
          type="button"
          aria-label="More options"
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((open) => !open)}
          className="inline-flex size-11 items-center justify-center rounded-sm hover:bg-surface-container"
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <circle cx="5" cy="12" r="1.8" />
            <circle cx="12" cy="12" r="1.8" />
            <circle cx="19" cy="12" r="1.8" />
          </svg>
        </button>
        {menuOpen && (
          <>
            <div className="fixed inset-0 z-20" onClick={() => setMenuOpen(false)} aria-hidden="true" />
            <div className="absolute top-full right-2 z-30 grid min-w-52 rounded-sm bg-surface-container-lowest p-1 shadow-lg">
              <button type="button" onClick={end} className="min-h-11 rounded-sm px-3 text-left hover:bg-surface-container">
                Change topics
              </button>
              {answered && (
                <button
                  type="button"
                  onClick={() => {
                    setMenuOpen(false);
                    openGuideline();
                  }}
                  className="min-h-11 rounded-sm px-3 text-left hover:bg-surface-container"
                >
                  Read guideline
                </button>
              )}
              {question && !reported && (
                <button
                  type="button"
                  onClick={() => {
                    setMenuOpen(false);
                    setReportOpen(true);
                  }}
                  className="min-h-11 rounded-sm px-3 text-left hover:bg-surface-container"
                >
                  Report a problem with this question
                </button>
              )}
            </div>
          </>
        )}
      </div>

      <div className="hidden flex-none items-center gap-4 rounded-sm bg-surface-container-low py-2 pr-2 pl-4 lg:flex">
        <div className="min-w-0 flex-1">
          <p className="font-headline text-lg font-semibold text-primary">
            {poolsLabel(selection)}
            {pickLabel && <span className="ml-2 font-body text-xs font-normal text-on-surface-variant">{pickLabel}</span>}
          </p>
          <p className="text-xs text-on-surface-variant">
            {scopeLabel} · {difficultyLabel}
          </p>
        </div>
        <button type="button" onClick={end} className="min-h-10 rounded-sm px-3 text-sm font-semibold text-primary underline">
          Change topics
        </button>
        {question && (
          <p className="flex gap-3 font-mono text-sm text-on-surface-variant">
            <span>Question {count}</span>
            <QuizTimer startedAt={startedAt} stoppedAt={stoppedAt} />
          </p>
        )}
        <button type="button" onClick={end} aria-keyshortcuts="Escape" className="min-h-10 rounded-sm bg-surface-container-high px-4 text-sm font-semibold">
          End
          <Kbd>Esc</Kbd>
        </button>
      </div>

      {error && (
        <p role="alert" className="mx-4 mt-3 flex-none rounded-sm bg-error-container p-3 text-sm text-error lg:mx-0">
          {error}
        </p>
      )}

      {!question && !exhausted && (
        <p className="m-auto text-on-surface-variant">{busy ? "Finding a question…" : "No question loaded."}</p>
      )}

      {!question && exhausted && (
        <section aria-labelledby="done-heading" className="m-4 space-y-3 rounded-sm bg-surface-container-low p-5 lg:mx-0 lg:mt-5">
          <h2 id="done-heading" className="font-headline text-xl font-semibold">
            You've seen every library question for these settings
          </h2>
          <div className="flex flex-wrap gap-2">
            {canGenerate && quota && (
              <button
                type="button"
                onClick={() => void generate()}
                disabled={busy !== null}
                className="min-h-10 rounded-sm bg-primary px-4 text-sm font-semibold text-on-primary disabled:opacity-50"
              >
                {busy === "generate" ? "Writing a question…" : `Generate a new question (${quota.generations.remaining} left this month)`}
                <Kbd light>↵</Kbd>
              </button>
            )}
            <button
              type="button"
              onClick={() => void nextQuestion(true)}
              disabled={busy !== null}
              className="min-h-10 rounded-sm bg-surface-container-high px-4 text-sm font-semibold disabled:opacity-50"
            >
              Go round again
            </button>
            <button type="button" onClick={end} className="min-h-10 rounded-sm px-3 text-sm font-semibold text-primary underline">
              Change topics
            </button>
          </div>
          {!signedIn && (
            <p className="text-sm text-on-surface-variant">
              <Link to="/sign-in" className="underline">
                Sign in
              </Link>{" "}
              to generate fresh questions when the library runs out.
            </p>
          )}
        </section>
      )}

      {question && (
        <article
          aria-labelledby="question-heading"
          className="grid min-h-0 flex-1 grid-rows-[auto_auto_minmax(0,1fr)_auto_auto] gap-x-6 px-4 pt-4 [grid-template-areas:'q'_'tabs'_'work'_'side'_'act'] lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)] lg:grid-rows-[auto_minmax(0,1fr)_auto] lg:px-0 lg:pt-5 lg:[grid-template-areas:'q_side'_'work_side'_'act_side']"
        >
          <div className="[grid-area:q]">
            <p className="mb-2 font-mono text-xs uppercase tracking-widest text-on-surface-variant">
              {question.origin === "live" ? "Newly generated" : "From the question library"} · {question.difficulty} · {question.documentTitle}
            </p>
            <h2
              id="question-heading"
              className={`mb-3 font-headline font-semibold text-pretty lg:mb-5 ${question.text.length > 220 ? "text-lg leading-snug lg:text-2xl" : "text-xl leading-snug lg:text-[1.75rem] lg:leading-tight"}`}
            >
              {question.text}
            </h2>
          </div>

          {marked && (
            <div role="group" aria-label="Show" className="mb-3 grid grid-cols-2 rounded-sm bg-surface-container-high p-1 [grid-area:tabs] lg:hidden">
              {(["marking", "source"] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  aria-pressed={tab === t}
                  onClick={() => setTab(t)}
                  className={`min-h-10 rounded-sm text-sm font-semibold ${tab === t ? "bg-surface-container-lowest text-on-surface" : "text-on-surface-variant"}`}
                >
                  {t === "marking" ? "Marking" : "Source"}
                </button>
              ))}
            </div>
          )}

          <div className={`min-h-0 flex-col [grid-area:work] lg:flex ${workPhone}`}>
            {!answered ? (
              <>
                <div className="mb-1 flex justify-between text-xs uppercase tracking-widest text-on-surface-variant">
                  <label htmlFor="quiz-answer">Your answer</label>
                  <span aria-hidden="true" className="hidden normal-case tracking-normal [@media(pointer:fine)]:inline">
                    Shift + Enter for a new line
                  </span>
                </div>
                <textarea
                  id="quiz-answer"
                  ref={answerBox}
                  value={answer}
                  onChange={(e) => setAnswer(e.target.value)}
                  onKeyDown={onAnswerKey}
                  readOnly={busy === "mark"}
                  maxLength={4000}
                  aria-keyshortcuts="Enter"
                  placeholder="Answer from memory…"
                  className="ruled min-h-24 w-full flex-1 resize-none outline-none read-only:text-on-surface-variant"
                />
              </>
            ) : (
              <>
                <p className="mb-1 text-xs uppercase tracking-widest text-on-surface-variant">Your answer</p>
                <div className="ruled mb-3 max-h-[30%] flex-none overflow-auto whitespace-pre-wrap text-on-surface-variant">
                  {submitted || "No answer typed."}
                </div>
                <SourcePanel
                  sourceText={result.sourceText}
                  sourceQuote={marked?.sourceQuote}
                  citation={result.citation}
                  documentId={result.documentId}
                  documentTitle={result.documentTitle}
                />
              </>
            )}
          </div>

          <aside aria-label="Marking" className={`min-h-0 flex-col gap-2 overflow-auto pb-3 lg:flex lg:pb-0 lg:[grid-area:side] ${sidePhone}`}>
            {busy === "mark" ? (
              <div className="space-y-3 rounded-sm bg-surface-container-low p-5" role="status">
                <p className="text-sm font-semibold">Marking your answer…</p>
                <div className="space-y-2" aria-hidden="true">
                  {["w-11/12", "w-3/4", "w-5/6", "w-3/5"].map((w) => (
                    <div key={w} className={`h-3 animate-pulse rounded-sm bg-surface-container-high motion-reduce:animate-none ${w}`} />
                  ))}
                </div>
              </div>
            ) : marked ? (
              <>
                <div className="rounded-sm bg-surface-container-low p-4 lg:p-5">
                  <MarkPanel
                    score={marked.score}
                    corrected={corrected}
                    summary={marked.feedbackSummary}
                    correctElements={marked.correctElements}
                    missingOrWrong={marked.missingOrWrong}
                    onCorrect={signedIn && marked.attemptId ? (s) => void correct(s) : null}
                    disabled={busy !== null}
                  />
                </div>
                {disclaimer}
              </>
            ) : answered ? (
              <>
                <div className="space-y-2 rounded-sm bg-surface-container-low p-4 lg:p-5">
                  {canSelfMark && <SelfMark value={selfScore} onChoose={(s) => void grade(s)} disabled={busy !== null} />}
                  <p className="hidden text-sm text-on-surface-variant lg:block">
                    Compare your answer with the guideline text. {canSelfMark ? "Your choice counts toward your progress." : ""}
                  </p>
                </div>
                <div className="hidden lg:block">{disclaimer}</div>
              </>
            ) : (
              <div className="flex flex-1 flex-col justify-center gap-3 rounded-sm p-6 outline-1 -outline-offset-1 outline-on-surface-variant/25 outline-dashed">
                <h3 className="font-headline text-xl font-semibold text-primary">{signedIn ? "Your marking appears here" : "Mark yourself here"}</h3>
                <p className="max-w-[40ch] text-on-surface-variant">
                  Answer from memory first. The guideline text then opens under your answer
                  {signedIn ? ", and the marking lands in this space." : " so you can compare and mark yourself."}
                </p>
                {!signedIn && (
                  <p className="text-sm">
                    <Link to="/sign-in" className="text-primary underline">
                      Sign in
                    </Link>{" "}
                    for AI marking.
                  </p>
                )}
                <p className="hidden text-sm text-on-surface-variant [@media(pointer:fine)]:block">
                  Press <kbd className="rounded-sm bg-on-surface/10 px-1.5 font-mono text-xs">?</kbd> for keyboard shortcuts.
                </p>
              </div>
            )}
          </aside>

          <div className="-mx-4 flex flex-none flex-wrap items-center gap-2 bg-surface px-4 pt-3 pb-[calc(0.75rem+env(safe-area-inset-bottom))] shadow-[0_-1px_0_rgb(0_0_0/0.08)] [grid-area:act] lg:mx-0 lg:px-0 lg:pb-0 lg:shadow-none">
            {!answered ? (
              <>
                {signedIn && (
                  <button
                    type="button"
                    onClick={() => void reveal()}
                    disabled={busy !== null}
                    aria-label={busy === "reveal" ? "Loading…" : "Reveal reference"}
                    aria-keyshortcuts="Alt+R"
                    className="min-h-12 flex-1 rounded-sm bg-surface-container-high px-4 text-sm font-semibold disabled:opacity-50 lg:min-h-10 lg:flex-none lg:bg-transparent lg:hover:bg-surface-container"
                  >
                    {busy === "reveal" ? (
                      "Loading…"
                    ) : (
                      <>
                        Reveal<span className="max-sm:hidden"> reference</span>
                      </>
                    )}
                    <Kbd>⌥R</Kbd>
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => void nextQuestion()}
                  disabled={busy !== null}
                  aria-keyshortcuts="Alt+S"
                  className="min-h-12 rounded-sm px-4 text-sm font-semibold hover:bg-surface-container disabled:opacity-50 lg:min-h-10"
                >
                  Skip
                  <Kbd>⌥S</Kbd>
                </button>
                <span className="hidden flex-1 lg:block" />
                {signedIn ? (
                  <button
                    type="button"
                    onClick={() => void mark()}
                    disabled={busy !== null || !answer.trim() || marksLeft === 0}
                    aria-label={busy === "mark" ? "Marking…" : `Mark my answer (${marksLeft} left)`}
                    aria-keyshortcuts="Enter"
                    className="min-h-12 flex-[2] rounded-sm bg-primary px-4 text-sm font-semibold text-on-primary disabled:opacity-50 lg:min-h-10 lg:flex-none"
                  >
                    {busy === "mark" ? (
                      "Marking…"
                    ) : (
                      <>
                        Mark<span className="max-sm:hidden"> my answer</span> ({marksLeft} left)
                      </>
                    )}
                    <Kbd light>↵</Kbd>
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => void reveal()}
                    disabled={busy !== null}
                    aria-keyshortcuts="Enter"
                    className="min-h-12 flex-[2] rounded-sm bg-primary px-4 text-sm font-semibold text-on-primary disabled:opacity-50 lg:min-h-10 lg:flex-none"
                  >
                    {busy === "reveal" ? "Loading…" : "Reveal reference"}
                    <Kbd light>↵</Kbd>
                  </button>
                )}
              </>
            ) : (
              <>
                <button
                  type="button"
                  onClick={() => setReportOpen(true)}
                  disabled={reported}
                  aria-keyshortcuts="F"
                  className="min-h-12 rounded-sm bg-surface-container-high px-4 text-sm font-semibold disabled:opacity-50 lg:min-h-10 lg:bg-transparent lg:hover:bg-surface-container"
                >
                  {reported ? "Reported" : "Report a problem"}
                  <Kbd>F</Kbd>
                </button>
                <a
                  href={documentPath(result.documentId)}
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-keyshortcuts="G"
                  className="hidden min-h-10 items-center rounded-sm px-4 text-sm font-semibold hover:bg-surface-container lg:inline-flex"
                >
                  Read guideline
                  <Kbd>G</Kbd>
                </a>
                <span className="hidden flex-1 lg:block" />
                <button
                  ref={nextButton}
                  type="button"
                  onClick={() => void nextQuestion()}
                  disabled={busy !== null && busy !== "grade"}
                  aria-keyshortcuts="Enter"
                  className="min-h-12 flex-1 rounded-sm bg-primary px-5 text-sm font-semibold text-on-primary disabled:opacity-50 lg:min-h-10 lg:flex-none"
                >
                  {busy === "next" ? "Finding a question…" : "Next question"}
                  <Kbd light>↵</Kbd>
                </button>
              </>
            )}
            {reported && (
              <p role="status" className="w-full text-sm text-on-surface-variant">
                Thanks. The question has been reported for review.
              </p>
            )}
          </div>
        </article>
      )}

      {reportOpen && question && (
        <ReportDialog
          questionId={question.id}
          onClose={closeReport}
          onSent={() => {
            setReportOpen(false);
            setReported(true);
          }}
        />
      )}
      {helpOpen && <ShortcutHelp onClose={closeHelp} />}
    </div>
  );
}
