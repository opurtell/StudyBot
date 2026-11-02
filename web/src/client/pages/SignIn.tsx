import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { api } from "../lib/api";
import { useSession } from "../lib/session";

export const SIGN_IN_ERRORS: Record<string, string> = {
  cancelled: "Sign-in was cancelled. Try again when you're ready.",
  expired: "That sign-in took too long or was started in another tab. Try again.",
  unverified_email: "Your Google account's email address isn't verified. Verify it with Google, then try again.",
  rate_limited: "Too many sign-in attempts. Wait a minute and try again.",
  unavailable: "Sign-in isn't available right now. Try again later.",
  failed: "Google sign-in didn't work. Try again.",
};

export function SignIn() {
  const [params] = useSearchParams();
  const errorCode = params.get("error");
  const error = errorCode ? (SIGN_IN_ERRORS[errorCode] ?? SIGN_IN_ERRORS.failed) : null;
  const [devSignIn, setDevSignIn] = useState(false);
  const { refresh } = useSession();
  const navigate = useNavigate();

  useEffect(() => {
    api
      .config()
      .then((cfg) => setDevSignIn(cfg.devSignIn))
      .catch(() => setDevSignIn(false));
  }, []);

  async function onDevSignIn() {
    await api.devSignIn();
    await refresh();
    navigate("/", { replace: true });
  }

  return (
    <section className="max-w-md space-y-5">
      <div className="space-y-2">
        <h1 className="font-headline text-3xl font-semibold">Sign in</h1>
        <p className="text-sm text-on-surface-variant">
          Sign in with your Google account. We only receive your email address. An account is created the first time
          you sign in.
        </p>
        <p className="text-sm text-on-surface-variant">
          Signing in lets AI mark your answers, which sends them to Google's Gemini service. Read the{" "}
          <Link to="/privacy" className="underline">
            privacy policy
          </Link>
          .
        </p>
      </div>
      {error && (
        <p role="alert" className="rounded-sm bg-error-container p-3 text-sm text-error">
          {error}
        </p>
      )}
      <a
        href="/api/auth/google/start"
        className="inline-flex w-full items-center justify-center gap-3 rounded-sm bg-primary px-4 py-3 text-sm font-semibold text-on-primary hover:opacity-90 sm:w-auto"
      >
        Continue with Google
      </a>
      {devSignIn && (
        <button
          type="button"
          onClick={onDevSignIn}
          className="block rounded-sm bg-surface-container-high px-4 py-2 text-sm font-semibold"
        >
          Dev sign-in (local only)
        </button>
      )}
    </section>
  );
}
