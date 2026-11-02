import { Link } from "react-router";
import { quizLink, Heatmap } from "../components/Heatmap";
import { HistoryList } from "../components/HistoryList";
import { ImportGuestProgress } from "../components/ImportGuestProgress";
import type { QuotaBucket } from "../lib/api";
import { useProgress } from "../lib/useProgress";
import { useSession } from "../lib/session";

function QuotaCard({ label, bucket }: { label: string; bucket: QuotaBucket }) {
  return (
    <div className="rounded-sm bg-surface-container-lowest p-4">
      <p className="text-xs font-medium uppercase tracking-widest text-on-surface-variant">{label}</p>
      <p className="mt-1 font-mono text-2xl">
        {bucket.remaining}
        <span className="text-base text-on-surface-variant"> / {bucket.limit} left</span>
      </p>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-sm bg-surface-container-lowest p-3 sm:p-4">
      <dt className="text-xs font-medium uppercase tracking-widest text-on-surface-variant">{label}</dt>
      <dd className="mt-1 font-mono text-xl sm:text-2xl">{value}</dd>
    </div>
  );
}

function ProgressSection() {
  const { data, error, loading, reload, signedIn } = useProgress();
  const started = Boolean(data && data.totals.answered + data.recent.length > 0);

  return (
    <>
      <ImportGuestProgress onImported={reload} />
      <section aria-labelledby="progress-heading" className="space-y-4">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 id="progress-heading" className="font-headline text-2xl font-semibold">
            Your progress
          </h2>
          {started && (
            <Link to="/history" className="text-sm underline">
              Answer history
            </Link>
          )}
        </div>
        {loading && !data && <p className="text-on-surface-variant">Loading…</p>}
        {error && (
          <p role="alert" className="rounded-sm bg-error-container p-3 text-sm text-error">
            {error}
          </p>
        )}
        {data && (
          <>
            {!signedIn && started && (
              <p className="text-sm text-on-surface-variant">
                Saved in this browser only.{" "}
                <Link to="/sign-in" className="underline">
                  Sign in
                </Link>{" "}
                to keep it on your account.
              </p>
            )}
            <dl className="grid grid-cols-3 gap-2 sm:gap-3">
              <Metric label="Answered" value={String(data.totals.answered)} />
              <Metric label="Accuracy" value={data.totals.accuracy === null ? "–" : `${Math.round(data.totals.accuracy)}%`} />
              <Metric label="Streak" value={`${data.totals.streakDays} ${data.totals.streakDays === 1 ? "day" : "days"}`} />
            </dl>
            {data.weakest && (
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-sm bg-surface-container-low p-4">
                <p className="text-sm">
                  <span className="block text-xs font-medium uppercase tracking-widest text-on-surface-variant">Focus next</span>
                  {data.weakest.section}
                  {data.weakest.documentTitle ? `: ${data.weakest.documentTitle}` : ""}
                </p>
                <Link
                  to={quizLink(data.weakest.section, data.weakest.documentId)}
                  className="min-h-11 rounded-sm bg-primary px-4 py-2 text-sm font-semibold text-on-primary hover:opacity-90"
                >
                  Practise this
                </Link>
              </div>
            )}
            <div className="space-y-2">
              <h3 className="text-xs font-medium uppercase tracking-widest text-on-surface-variant">Knowledge heatmap</h3>
              <Heatmap sections={data.sections} />
            </div>
            {data.recent.length > 0 && (
              <div className="space-y-2">
                <h3 className="text-xs font-medium uppercase tracking-widest text-on-surface-variant">Recent answers</h3>
                <HistoryList entries={data.recent.map((r) => ({ ...r, href: signedIn ? `/history/${r.id}` : undefined }))} />
              </div>
            )}
          </>
        )}
      </section>
    </>
  );
}

export function Home() {
  const { me, loading, error } = useSession();
  if (loading) return <p className="text-on-surface-variant">Loading…</p>;

  return (
    <div className="space-y-8">
      <section className="space-y-3">
        <h1 className="font-headline text-3xl font-semibold leading-tight sm:text-4xl">Active recall for the ACTAS CMGs</h1>
        <p className="text-on-surface-variant">
          Practise with questions drawn from the ACT Ambulance Service Clinical Management Guidelines, with the source
          shown for every answer.
        </p>
        <Link
          to="/quiz"
          className="inline-block min-h-11 rounded-sm bg-primary px-5 py-3 font-semibold text-on-primary hover:opacity-90"
        >
          Start a quiz
        </Link>
      </section>

      {error && (
        <p role="alert" className="rounded-sm bg-error-container p-3 text-sm text-error">
          {error}
        </p>
      )}

      <ProgressSection />

      {me?.signedIn ? (
        <section aria-labelledby="quota-heading" className="space-y-4 rounded-sm bg-surface-container-low p-5">
          <h2 id="quota-heading" className="font-headline text-xl font-semibold">
            Signed in as {me.email}
          </h2>
          <p className="text-sm text-on-surface-variant">
            Library questions are unlimited. Your free allowance this month covers fresh questions and AI marking.
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            <QuotaCard label="New questions" bucket={me.quota.generations} />
            <QuotaCard label="AI marking" bucket={me.quota.marking} />
          </div>
        </section>
      ) : (
        <section aria-labelledby="guest-heading" className="space-y-3 rounded-sm bg-surface-container-low p-5">
          <h2 id="guest-heading" className="font-headline text-xl font-semibold">
            You're studying as a guest
          </h2>
          <p className="text-sm text-on-surface-variant">
            Guests get questions from the library, check their own answers against the guideline, and keep progress in
            this browser. Sign in for AI marking, freshly generated questions and progress that follows you.
          </p>
          <Link
            to="/sign-in"
            className="inline-block min-h-11 rounded-sm bg-primary px-4 py-2 text-sm font-semibold text-on-primary hover:opacity-90"
          >
            Sign in with Google
          </Link>
        </section>
      )}

      <section aria-labelledby="browse-heading" className="space-y-3">
        <h2 id="browse-heading" className="font-headline text-xl font-semibold">
          Read the source
        </h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <Link to="/guidelines" className="rounded-sm bg-surface-container-lowest p-4 hover:bg-surface-container">
            <span className="block font-semibold">Clinical guidelines</span>
            <span className="text-sm text-on-surface-variant">CMGs and clinical skills, filtered to AP or ICP scope.</span>
          </Link>
          <Link to="/medications" className="rounded-sm bg-surface-container-lowest p-4 hover:bg-surface-container">
            <span className="block font-semibold">Medications</span>
            <span className="text-sm text-on-surface-variant">Medicine monographs with doses.</span>
          </Link>
        </div>
      </section>
    </div>
  );
}
