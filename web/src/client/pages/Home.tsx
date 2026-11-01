import { Link } from "react-router";
import type { QuotaBucket } from "../lib/api";
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
      </section>

      {error && (
        <p role="alert" className="rounded-sm bg-error-container p-3 text-sm text-error">
          {error}
        </p>
      )}

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
            Guests get questions from the library and check their own answers against the guideline. Sign in for AI
            marking and freshly generated questions.
          </p>
          <Link
            to="/sign-in"
            className="inline-block rounded-sm bg-primary px-4 py-2 text-sm font-semibold text-on-primary hover:opacity-90"
          >
            Sign in with email
          </Link>
        </section>
      )}

      <p className="text-sm text-on-surface-variant">The quiz is on its way. This build sets up accounts and sign-in.</p>
    </div>
  );
}
