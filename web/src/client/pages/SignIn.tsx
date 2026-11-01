import { useEffect, useState, type FormEvent } from "react";
import { Turnstile } from "../components/Turnstile";
import { api, ApiError } from "../lib/api";

export function SignIn() {
  const [siteKey, setSiteKey] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [token, setToken] = useState<string | null>(null);
  const [resetKey, setResetKey] = useState(0);
  const [status, setStatus] = useState<"idle" | "sending" | "sent">("idle");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .config()
      .then((cfg) => setSiteKey(cfg.turnstileSiteKey))
      .catch(() => setError("Couldn't reach the server. Check your connection and reload."));
  }, []);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!token) {
      setError("Wait for the human check to finish, then try again.");
      return;
    }
    setStatus("sending");
    setError(null);
    try {
      await api.requestMagicLink(email, token);
      setStatus("sent");
    } catch (err) {
      setStatus("idle");
      setToken(null);
      setResetKey((k) => k + 1);
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again shortly.");
    }
  }

  if (status === "sent") {
    return (
      <section className="space-y-3" aria-live="polite">
        <h1 className="font-headline text-3xl font-semibold">Check your email</h1>
        <p className="text-on-surface-variant">
          If <strong>{email}</strong> can receive mail, a sign-in link is on its way. It works once and expires in 15
          minutes. Open it on this device.
        </p>
      </section>
    );
  }

  return (
    <section className="max-w-md space-y-5">
      <div className="space-y-2">
        <h1 className="font-headline text-3xl font-semibold">Sign in</h1>
        <p className="text-sm text-on-surface-variant">
          We'll email you a sign-in link. No password needed. A new account is created the first time you sign in.
        </p>
      </div>
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <div className="space-y-1">
          <label htmlFor="email" className="block text-xs font-medium uppercase tracking-widest text-on-surface-variant">
            Email
          </label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            inputMode="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full border-0 border-b-2 border-outline-variant bg-transparent px-0 py-2 text-base focus:border-primary focus:outline-none"
          />
        </div>
        {siteKey && (
          <Turnstile
            siteKey={siteKey}
            resetKey={resetKey}
            onToken={setToken}
            onError={(message) => setError(message)}
          />
        )}
        {error && (
          <p role="alert" className="rounded-sm bg-error-container p-3 text-sm text-error">
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={status === "sending" || !email}
          className="w-full rounded-sm bg-primary px-4 py-3 text-sm font-semibold text-on-primary hover:opacity-90 disabled:opacity-50 sm:w-auto"
        >
          {status === "sending" ? "Sending…" : "Email me a sign-in link"}
        </button>
      </form>
    </section>
  );
}
