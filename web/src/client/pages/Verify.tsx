import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";
import { api, ApiError } from "../lib/api";
import { useSession } from "../lib/session";

function readTokenFromHash(): string | null {
  return new URLSearchParams(window.location.hash.slice(1)).get("token");
}

export function Verify() {
  const [token] = useState(readTokenFromHash);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { refresh } = useSession();
  const navigate = useNavigate();

  useEffect(() => {
    if (window.location.hash) window.history.replaceState(null, "", window.location.pathname);
  }, []);

  async function confirm() {
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      await api.verify(token);
      await refresh();
      navigate("/", { replace: true });
    } catch (err) {
      setBusy(false);
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again shortly.");
    }
  }

  if (!token) {
    return (
      <section className="space-y-3">
        <h1 className="font-headline text-3xl font-semibold">Link not recognised</h1>
        <p className="text-on-surface-variant">Open the link from your email again, or request a new one.</p>
        <Link to="/sign-in" className="underline">
          Request a new link
        </Link>
      </section>
    );
  }

  return (
    <section className="max-w-md space-y-4">
      <h1 className="font-headline text-3xl font-semibold">Finish signing in</h1>
      <p className="text-on-surface-variant">Confirm to sign in on this device.</p>
      {error && (
        <div role="alert" className="space-y-2 rounded-sm bg-error-container p-3 text-sm text-error">
          <p>{error}</p>
          <Link to="/sign-in" className="underline">
            Request a new link
          </Link>
        </div>
      )}
      <button
        type="button"
        onClick={confirm}
        disabled={busy || Boolean(error)}
        className="w-full rounded-sm bg-primary px-4 py-3 text-sm font-semibold text-on-primary hover:opacity-90 disabled:opacity-50 sm:w-auto"
      >
        {busy ? "Signing in…" : "Sign in"}
      </button>
    </section>
  );
}
