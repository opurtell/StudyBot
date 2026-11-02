import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";
import { Feedback, ScoreBadge } from "../components/Feedback";
import { HistoryList } from "../components/HistoryList";
import { api, type HistoryItem } from "../lib/api";
import { useGuestAttempts } from "../lib/guestProgress";
import { useSession } from "../lib/session";
import { useLoad } from "../lib/useLoad";

function AccountHistory() {
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [more, setMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load(before?: number) {
    setLoading(true);
    setError(null);
    try {
      const page = await api.history(before);
      setItems((prev) => (before ? [...prev, ...page.items] : page.items));
      setMore(page.more);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't load your history.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  return (
    <>
      {error && (
        <p role="alert" className="rounded-sm bg-error-container p-3 text-sm text-error">
          {error}
        </p>
      )}
      {!loading && !error && items.length === 0 && <Empty />}
      <HistoryList entries={items.map((i) => ({ ...i, href: `/history/${i.id}` }))} />
      {loading && <p className="text-on-surface-variant">Loading…</p>}
      {more && !loading && (
        <button
          type="button"
          onClick={() => void load(items.at(-1)?.at)}
          className="min-h-11 rounded-sm bg-surface-container-high px-4 py-2 text-sm font-semibold"
        >
          Show older answers
        </button>
      )}
    </>
  );
}

function Empty() {
  return (
    <p className="text-on-surface-variant">
      Nothing yet.{" "}
      <Link to="/quiz" className="underline">
        Start a quiz
      </Link>{" "}
      and your answers will appear here.
    </p>
  );
}

function GuestHistory() {
  const { attempts } = useGuestAttempts();
  const entries = [...attempts].reverse().map((a) => ({ ...a, kind: "revealed" as const }));
  return (
    <>
      <p className="text-sm text-on-surface-variant">
        Saved in this browser only.{" "}
        <Link to="/sign-in" className="underline">
          Sign in
        </Link>{" "}
        to keep your answers on your account.
      </p>
      {entries.length === 0 ? <Empty /> : <HistoryList entries={entries} />}
    </>
  );
}

export function History() {
  const { me, loading } = useSession();
  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="font-headline text-3xl font-semibold">Answer history</h1>
        <p className="text-on-surface-variant">Every question you've answered, newest first.</p>
      </header>
      {loading ? <p className="text-on-surface-variant">Loading…</p> : me?.signedIn ? <AccountHistory /> : <GuestHistory />}
    </div>
  );
}

const dateFormat = new Intl.DateTimeFormat("en-AU", { dateStyle: "medium", timeStyle: "short" });

export function AttemptView() {
  const { id = "" } = useParams();
  const { data, error, loading } = useLoad(() => api.attempt(id), [id]);

  return (
    <div className="space-y-6">
      <Link to="/history" className="text-sm underline">
        ← Answer history
      </Link>
      {loading && <p className="text-on-surface-variant">Loading…</p>}
      {error && (
        <p role="alert" className="rounded-sm bg-error-container p-3 text-sm text-error">
          {error}
        </p>
      )}
      {data && (
        <article aria-labelledby="attempt-heading" className="space-y-4 rounded-sm bg-surface-container-lowest p-4 sm:p-5">
          <p className="font-mono text-xs uppercase tracking-widest text-on-surface-variant">
            {data.section} · {data.question.difficulty} · {dateFormat.format(data.at)}
            {data.elapsedMs ? ` · ${Math.round(data.elapsedMs / 1000)} s` : ""}
          </p>
          <h1 id="attempt-heading" className="font-headline text-xl font-semibold leading-snug sm:text-2xl">
            {data.question.text}
          </h1>
          {data.question.withdrawn && (
            <p className="rounded-sm bg-surface-container-low p-3 text-sm">
              This question has since been withdrawn for review.
            </p>
          )}
          {data.kind === "revealed" && (
            <p className="text-sm text-on-surface-variant">
              {data.score ? (
                <>
                  You checked this against the reference. <ScoreBadge score={data.score} self />
                </>
              ) : (
                "You revealed the reference without marking yourself."
              )}
            </p>
          )}
          <h2 className="sr-only">Your result</h2>
          <Feedback
            answer={data.answer}
            data={{
              marked: data.kind === "marked",
              score: data.score,
              ...(data.evaluation ?? {}),
              sourceText: data.sourceText,
              citation: data.citation,
              documentId: data.documentId,
              documentTitle: data.documentTitle,
            }}
          />
          <Link to={`/quiz?document=${encodeURIComponent(data.documentId)}`} className="inline-block text-sm underline">
            More questions on {data.documentTitle}
          </Link>
        </article>
      )}
    </div>
  );
}
