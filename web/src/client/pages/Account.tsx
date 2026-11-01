import { useState } from "react";
import { Navigate } from "react-router";
import { api } from "../lib/api";
import { useSession } from "../lib/session";

export function Account() {
  const { me, loading, signOut, refresh } = useSession();
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [leaving, setLeaving] = useState(false);

  if (loading) return <p className="text-on-surface-variant">Loading…</p>;
  if (!me?.signedIn) return <Navigate to={leaving ? "/" : "/sign-in"} replace />;

  async function onSignOut() {
    setLeaving(true);
    await signOut();
  }

  async function onDelete() {
    try {
      await api.deleteAccount();
      setLeaving(true);
      await refresh();
    } catch {
      setError("Couldn't delete your account. Try again shortly.");
    }
  }

  return (
    <div className="space-y-8">
      <section className="space-y-2">
        <h1 className="font-headline text-3xl font-semibold">Account</h1>
        <p className="text-on-surface-variant">
          Signed in as <strong>{me.email}</strong>
        </p>
        <button type="button" onClick={onSignOut} className="rounded-sm bg-surface-container-high px-4 py-2 text-sm font-semibold">
          Sign out
        </button>
      </section>

      <section aria-labelledby="delete-heading" className="space-y-3 rounded-sm bg-surface-container-low p-5">
        <h2 id="delete-heading" className="font-headline text-xl font-semibold">
          Delete account
        </h2>
        <p className="text-sm text-on-surface-variant">
          This removes your account, your study history and your sign-in sessions. It can't be undone.
        </p>
        {error && (
          <p role="alert" className="text-sm text-error">
            {error}
          </p>
        )}
        {confirming ? (
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={onDelete} className="rounded-sm bg-error px-4 py-2 text-sm font-semibold text-white">
              Yes, delete my account
            </button>
            <button type="button" onClick={() => setConfirming(false)} className="rounded-sm px-4 py-2 text-sm font-semibold">
              Cancel
            </button>
          </div>
        ) : (
          <button type="button" onClick={() => setConfirming(true)} className="rounded-sm px-4 py-2 text-sm font-semibold text-error">
            Delete account…
          </button>
        )}
      </section>
    </div>
  );
}
