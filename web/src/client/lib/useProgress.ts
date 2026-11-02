import { useCallback, useEffect, useState } from "react";
import { summariseProgress } from "../../shared/progress";
import { api, type Progress } from "./api";
import { toProgressRows, useGuestAttempts } from "./guestProgress";
import { useScopeChoice, viewFor } from "./scopeView";
import { useSession } from "./session";

export function useProgress() {
  const { me, loading: sessionLoading } = useSession();
  const [choice] = useScopeChoice();
  const view = viewFor(choice);
  const signedIn = Boolean(me?.signedIn);
  const { attempts } = useGuestAttempts();
  const [data, setData] = useState<Progress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  const reload = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    if (sessionLoading) return;
    let live = true;
    setLoading(true);
    setError(null);
    const load = signedIn
      ? api.progress(view)
      : api.topics(view).then(({ topics }) => {
          const summary = summariseProgress(toProgressRows(attempts), topics, {
            now: Date.now(),
            tzOffsetMinutes: new Date().getTimezoneOffset(),
          });
          const recent = [...attempts]
            .reverse()
            .slice(0, 5)
            .map((a) => ({ ...a, kind: "revealed" as const }));
          return { ...summary, recent };
        });
    load
      .then((value) => {
        if (live) setData(value);
      })
      .catch((err: unknown) => {
        if (live) setError(err instanceof Error ? err.message : "Couldn't load your progress.");
      })
      .finally(() => {
        if (live) setLoading(false);
      });
    return () => {
      live = false;
    };
  }, [sessionLoading, signedIn, view, attempts, tick]);

  return { data, error, loading, reload, signedIn };
}
