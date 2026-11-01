import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router";
import { ScopePicker } from "../components/ScopePicker";
import {
  api,
  ApiError,
  type Difficulty,
  type DocumentSummary,
  type Mark,
  type Quota,
  type QuizFilters,
  type QuizQuestion,
  type ReportReason,
  type Reveal,
} from "../lib/api";
import { useScopeChoice, viewFor } from "../lib/scopeView";
import { useSession } from "../lib/session";

const SEEN_KEY = "quiz-seen";
const MAX_SEEN = 400;

const SCORE_LABEL: Record<Mark["score"], string> = { correct: "Correct", partial: "Partly correct", incorrect: "Incorrect" };
const SCORE_CLASS: Record<Mark["score"], string> = {
  correct: "bg-primary text-on-primary",
  partial: "bg-highlight text-on-highlight",
  incorrect: "bg-error text-white",
};

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
  const [choice, setChoice] = useScopeChoice();
  const view = viewFor(choice);
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [documentId, setDocumentId] = useState("");
  const [difficulty, setDifficulty] = useState<Difficulty | "">("");

  const [question, setQuestion] = useState<QuizQuestion | null>(null);
  const [questionView, setQuestionView] = useState(view);
  const [exhausted, setExhausted] = useState(false);
  const [canGenerate, setCanGenerate] = useState(false);
  const [quota, setQuota] = useState<Quota | null>(null);
  const [answer, setAnswer] = useState("");
  const [result, setResult] = useState<Mark | Reveal | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const started = useRef(Date.now());

  useEffect(() => {
    let live = true;
    Promise.all([api.guidelines(), api.medications()])
      .then(([g, m]) => {
        if (live) setDocuments([...g.items, ...m.items]);
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, []);

  useEffect(() => {
    if (me?.signedIn) setQuota(me.quota);
  }, [me]);

  const filters: QuizFilters = { view, documentId: documentId || null, difficulty: difficulty || null };

  function show(next: QuizQuestion | null) {
    setQuestion(next);
    setQuestionView(view);
    setAnswer("");
    setResult(null);
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
      if (question) setResult(await api.reveal(question.id, questionView));
    });

  const mark = (e: FormEvent) => {
    e.preventDefault();
    return run("mark", async () => {
      if (!question) return;
      try {
        const res = await api.mark(question.id, questionView, answer, Date.now() - started.current);
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

      <section aria-label="Quiz settings" className="space-y-3">
        <ScopePicker choice={choice} onChange={setChoice} legend="Questions for" label="Scope" />
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block text-sm">
            <span className="mb-1 block font-medium">Guideline</span>
            <select
              value={documentId}
              onChange={(e) => setDocumentId(e.target.value)}
              className="w-full rounded-sm bg-surface-container-lowest p-2"
            >
              <option value="">Any guideline</option>
              {documents.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.kind === "csm" ? d.number : `${d.kind === "med" ? "MED" : "CMG"} ${d.number}`} {d.title}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="mb-1 block font-medium">Difficulty</span>
            <select
              value={difficulty}
              onChange={(e) => setDifficulty(e.target.value as Difficulty | "")}
              className="w-full rounded-sm bg-surface-container-lowest p-2"
            >
              <option value="">Any difficulty</option>
              <option value="easy">Easy</option>
              <option value="medium">Medium</option>
              <option value="hard">Hard</option>
            </select>
          </label>
        </div>
        <button
          type="button"
          onClick={() => void nextQuestion()}
          disabled={busy !== null}
          className="rounded-sm bg-primary px-4 py-2 text-sm font-semibold text-on-primary disabled:opacity-50"
        >
          {busy === "next" ? "Finding a question…" : question || result ? "Next question" : "Start"}
        </button>
      </section>

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

          {result && <Feedback result={result} />}

          <ReportQuestion key={question.id} questionId={question.id} />
        </article>
      )}
    </div>
  );
}

function Feedback({ result }: { result: Mark | Reveal }) {
  const marked = "score" in result;
  return (
    <section aria-label="Feedback" className="space-y-4">
      {marked && (
        <div className="space-y-3">
          <p>
            <span className={`rounded-sm px-2 py-1 text-sm font-semibold ${SCORE_CLASS[result.score]}`}>{SCORE_LABEL[result.score]}</span>
          </p>
          {result.feedbackSummary && <p>{result.feedbackSummary}</p>}
          {result.correctElements.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold">What you got right</h3>
              <ul className="list-disc pl-5 text-sm">
                {result.correctElements.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            </div>
          )}
          {result.missingOrWrong.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold">Missing or wrong</h3>
              <ul className="list-disc pl-5 text-sm">
                {result.missingOrWrong.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            </div>
          )}
          {result.sourceQuote && (
            <blockquote className="border-l-4 border-highlight pl-3 text-sm italic">{result.sourceQuote}</blockquote>
          )}
        </div>
      )}
      <div className="space-y-2 rounded-sm bg-surface-container-low p-4">
        <h3 className="text-sm font-semibold">From the source</h3>
        <p className="whitespace-pre-wrap text-sm">{result.sourceText}</p>
        <p className="text-xs text-on-surface-variant">
          Ref: {result.citation} ·{" "}
          <Link
            to={`/${result.documentId.startsWith("MED_") ? "medications" : "guidelines"}/${encodeURIComponent(result.documentId)}`}
            className="underline"
          >
            Read {result.documentTitle}
          </Link>
        </p>
      </div>
    </section>
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
