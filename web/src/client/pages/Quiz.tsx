import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router";
import { Feedback, SelfGrade } from "../components/Feedback";
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
  type ReportReason,
  type Reveal,
  type Score,
  type Topic,
} from "../lib/api";
import { gradeGuestAttempt, recordGuestAttempt } from "../lib/guestProgress";
import { usePreferences } from "../lib/preferences";
import { buildGroups, EVERYTHING, poolsLabel, resolveSelection, selectionFromLink, type Selection } from "../lib/quizSelection";
import { QUIZ_SCOPE_OPTIONS, quizScopeName, useQuizScope, viewFor } from "../lib/scopeView";
import { useSession } from "../lib/session";

const SEEN_KEY = "quiz-seen";
const MAX_SEEN = 400;

const DIFFICULTIES: { value: Difficulty | ""; label: string }[] = [
  { value: "", label: "Any" },
  { value: "easy", label: "Easy" },
  { value: "medium", label: "Medium" },
  { value: "hard", label: "Hard" },
];

const REASONS: { value: ReportReason; label: string }[] = [
  { value: "incorrect", label: "Clinically wrong" },
  { value: "not_in_source", label: "Answer isn't in the guideline" },
  { value: "out_of_scope", label: "Outside my scope of practice" },
  { value: "unclear", label: "Unclear or badly worded" },
  { value: "other", label: "Something else" },
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

  const mark = (e: FormEvent) => {
    e.preventDefault();
    return run("mark", async () => {
      if (!question) return;
      try {
        const res = await api.mark(question.id, questionView, answer, Date.now() - started.current);
        setSubmitted(answer.trim());
        setResult(res);
        setQuota(res.quota);
        void refresh();
      } catch (err) {
        if (err instanceof ApiError && err.code === "quota_exhausted") void refresh();
        throw err;
      }
    });
  };

  const marksLeft = quota?.marking.remaining ?? 0;

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="font-headline text-3xl font-semibold">Quiz</h1>
        <p className="text-on-surface-variant">
          Questions come from the ACTAS guidelines. Answer from memory, then check against the source.
        </p>
      </header>

      {pickerOpen ? (
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
                disabled={busy !== null || (linkApplied && groups.length > 0 && resolved.inPlay.length === 0)}
                className="min-h-12 w-full rounded-sm bg-primary px-5 text-base font-semibold text-on-primary disabled:opacity-50"
              >
                {busy === "next" ? "Finding a question…" : "Start"}
              </button>
            ),
          }}
        />
      ) : (
        <section aria-label="Quiz topics" className="flex flex-wrap items-center gap-3 rounded-sm bg-surface-container-low p-3">
          <div className="min-w-0 flex-1">
            <p className="font-headline text-lg font-semibold text-primary">{poolsLabel(selection)}</p>
            <p className="text-xs text-on-surface-variant">
              {scopeLabel} · {difficultyLabel}
              {pickCount > 0 && ` · ${pickCount} ${selection.mode === "only" ? "picked" : "left out"}`}
            </p>
          </div>
          <button type="button" onClick={() => setPickerOpen(true)} className="min-h-10 rounded-sm px-3 text-sm font-semibold text-primary underline">
            Change topics
          </button>
          <button
            type="button"
            onClick={() => void nextQuestion()}
            disabled={busy !== null}
            className="min-h-10 rounded-sm bg-primary px-4 text-sm font-semibold text-on-primary disabled:opacity-50"
          >
            {busy === "next" ? "Finding a question…" : "Next question"}
          </button>
        </section>
      )}

      {error && (
        <p role="alert" className="rounded-sm bg-error-container p-3 text-sm text-error">
          {error}
        </p>
      )}

      {exhausted && !question && (
        <section aria-labelledby="done-heading" className="space-y-3 rounded-sm bg-surface-container-low p-5">
          <h2 id="done-heading" className="font-headline text-xl font-semibold">
            You've seen every library question for these settings
          </h2>
          <div className="flex flex-wrap gap-2">
            {canGenerate && quota && (
              <button
                type="button"
                onClick={() => void generate()}
                disabled={busy !== null}
                className="rounded-sm bg-primary px-4 py-2 text-sm font-semibold text-on-primary disabled:opacity-50"
              >
                {busy === "generate" ? "Writing a question…" : `Generate a new question (${quota.generations.remaining} left this month)`}
              </button>
            )}
            <button
              type="button"
              onClick={() => void nextQuestion(true)}
              disabled={busy !== null}
              className="rounded-sm bg-surface-container-high px-4 py-2 text-sm font-semibold disabled:opacity-50"
            >
              Go round again
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
        <article aria-labelledby="question-heading" className="space-y-4 rounded-sm bg-surface-container-lowest p-5">
          <p className="font-mono text-xs uppercase tracking-widest text-on-surface-variant">
            {question.origin === "live" ? "Newly generated" : "From the question library"} · {question.difficulty} ·{" "}
            {question.documentTitle}
          </p>
          <h2 id="question-heading" className="font-headline text-xl font-semibold leading-snug">
            {question.text}
          </h2>

          {!result && (
            <form onSubmit={(e) => void mark(e)} className="space-y-3">
              <label className="block text-sm">
                <span className="mb-1 block font-medium">Your answer</span>
                <textarea
                  value={answer}
                  onChange={(e) => setAnswer(e.target.value)}
                  rows={5}
                  maxLength={4000}
                  className="w-full rounded-sm bg-surface-container-low p-2"
                />
              </label>
              <div className="flex flex-wrap items-center gap-2">
                {signedIn && (
                  <button
                    type="submit"
                    disabled={busy !== null || !answer.trim() || marksLeft === 0}
                    className="rounded-sm bg-primary px-4 py-2 text-sm font-semibold text-on-primary disabled:opacity-50"
                  >
                    {busy === "mark" ? "Marking…" : `Mark my answer (${marksLeft} left)`}
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => void reveal()}
                  disabled={busy !== null}
                  className="rounded-sm bg-surface-container-high px-4 py-2 text-sm font-semibold disabled:opacity-50"
                >
                  {busy === "reveal" ? "Loading…" : "Reveal reference"}
                </button>
              </div>
              {!signedIn && (
                <p className="text-sm text-on-surface-variant">
                  <Link to="/sign-in" className="underline">
                    Sign in
                  </Link>{" "}
                  for AI marking. Guests check their own answer against the reference.
                </p>
              )}
            </form>
          )}

          {result && (
            <Feedback
              answer={submitted}
              data={{
                marked: "correctElements" in result,
                score: "correctElements" in result ? result.score : null,
                ...("correctElements" in result
                  ? {
                      feedbackSummary: result.feedbackSummary,
                      correctElements: result.correctElements,
                      missingOrWrong: result.missingOrWrong,
                      sourceQuote: result.sourceQuote,
                    }
                  : {}),
                sourceText: result.sourceText,
                citation: result.citation,
                documentId: result.documentId,
                documentTitle: result.documentTitle,
              }}
            />
          )}
          {result && !("correctElements" in result) && (signedIn ? Boolean(result.attemptId) : true) && (
            <SelfGrade value={selfScore} onChoose={(s) => void grade(s)} disabled={busy !== null} />
          )}

          <ReportQuestion key={question.id} questionId={question.id} />
        </article>
      )}
    </div>
  );
}

function ReportQuestion({ questionId }: { questionId: string }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState<ReportReason | "">("");
  const [detail, setDetail] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "sent">("idle");
  const [error, setError] = useState<string | null>(null);

  if (state === "sent") {
    return (
      <p role="status" className="text-sm text-on-surface-variant">
        Thanks. The question has been reported for review.
      </p>
    );
  }
  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)} className="text-sm text-on-surface-variant underline">
        Report a problem with this question
      </button>
    );
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!reason) return;
    setState("sending");
    setError(null);
    try {
      await api.report(questionId, reason, detail);
      setState("sent");
    } catch (err) {
      setError(message(err));
      setState("idle");
    }
  }

  return (
    <form onSubmit={(e) => void submit(e)} className="space-y-3 rounded-sm bg-surface-container-low p-4">
      <fieldset className="space-y-1">
        <legend className="text-sm font-semibold">What's wrong?</legend>
        {REASONS.map((r) => (
          <label key={r.value} className="flex items-center gap-2 text-sm">
            <input type="radio" name="reason" value={r.value} checked={reason === r.value} onChange={() => setReason(r.value)} />
            {r.label}
          </label>
        ))}
      </fieldset>
      <label className="block text-sm">
        <span className="mb-1 block">Details (optional)</span>
        <textarea
          value={detail}
          onChange={(e) => setDetail(e.target.value)}
          rows={2}
          maxLength={1000}
          className="w-full rounded-sm bg-surface-container-lowest p-2"
        />
      </label>
      {error && (
        <p role="alert" className="text-sm text-error">
          {error}
        </p>
      )}
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={!reason || state === "sending"}
          className="rounded-sm bg-primary px-4 py-2 text-sm font-semibold text-on-primary disabled:opacity-50"
        >
          {state === "sending" ? "Sending…" : "Send report"}
        </button>
        <button type="button" onClick={() => setOpen(false)} className="rounded-sm px-4 py-2 text-sm font-semibold">
          Cancel
        </button>
      </div>
    </form>
  );
}
