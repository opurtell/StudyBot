import { useState } from "react";
import { api } from "../lib/api";
import { toImport, useGuestAttempts } from "../lib/guestProgress";
import { useSession } from "../lib/session";

const BATCH = 150;

export function ImportGuestProgress({ onImported }: { onImported?: () => void }) {
  const { me } = useSession();
  const { attempts, clear } = useGuestAttempts();
  const [state, setState] = useState<"idle" | "busy" | "done">("idle");
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (state === "done" && result) {
    return (
      <p role="status" className="rounded-sm bg-primary-fixed p-3 text-sm">
        {result}
      </p>
    );
  }
  if (!me?.signedIn || attempts.length === 0) return null;

  async function importAll() {
    setState("busy");
    setError(null);
    try {
      const all = toImport(attempts);
      let imported = 0;
      for (let i = 0; i < all.length; i += BATCH) {
        imported += (await api.importProgress(all.slice(i, i + BATCH))).imported;
      }
      clear();
      setResult(`Added ${imported} ${imported === 1 ? "answer" : "answers"} to your account.`);
      setState("done");
      onImported?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't add your progress. Try again shortly.");
      setState("idle");
    }
  }

  return (
    <section aria-labelledby="import-heading" className="space-y-3 rounded-sm bg-primary-fixed p-4">
      <h2 id="import-heading" className="font-headline text-lg font-semibold">
        Keep your guest progress?
      </h2>
      <p className="text-sm">
        You answered {attempts.length} {attempts.length === 1 ? "question" : "questions"} as a guest on this device. Add them to
        your account so your progress follows you.
      </p>
      {error && (
        <p role="alert" className="text-sm text-error">
          {error}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => void importAll()}
          disabled={state === "busy"}
          className="min-h-11 rounded-sm bg-primary px-4 py-2 text-sm font-semibold text-on-primary disabled:opacity-50"
        >
          {state === "busy" ? "Adding…" : "Add to my account"}
        </button>
        <button type="button" onClick={clear} disabled={state === "busy"} className="min-h-11 rounded-sm px-4 py-2 text-sm font-semibold">
          Discard
        </button>
      </div>
    </section>
  );
}
