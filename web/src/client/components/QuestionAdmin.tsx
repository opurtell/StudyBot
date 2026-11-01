import { useEffect, useState } from "react";
import { api, type QuestionAdminStatus } from "../lib/api";

export function QuestionAdmin() {
  const [status, setStatus] = useState<QuestionAdminStatus | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function refresh() {
    try {
      setStatus(await api.questionAdmin());
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Couldn't load the question bank.");
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function act(fn: () => Promise<unknown>, done: string) {
    setBusy(true);
    setMessage(null);
    try {
      await fn();
      setMessage(done);
      await refresh();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "That didn't work.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="bank-heading" className="space-y-4 rounded-sm bg-surface-container-low p-5">
      <h2 id="bank-heading" className="font-headline text-xl font-semibold">
        Question bank
      </h2>
      {!status ? (
        <p className="text-sm text-on-surface-variant">Loading…</p>
      ) : (
        <>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1 font-mono text-sm">
            <dt>Active</dt>
            <dd>{status.summary.byStatus.active ?? 0}</dd>
            <dt>Withdrawn</dt>
            <dd>{status.summary.byStatus.flagged ?? 0}</dd>
            <dt>Retired</dt>
            <dd>{status.summary.byStatus.retired ?? 0}</dd>
            <dt>AP / ICP visible</dt>
            <dd>
              {status.summary.activeByView.ap} / {status.summary.activeByView.icp}
            </dd>
            <dt>Generated live</dt>
            <dd>{status.summary.live}</dd>
            <dt>Today</dt>
            <dd>
              {status.today.generations}/{status.today.caps.gen} new, {status.today.marks}/{status.today.caps.eval} marks
            </dd>
            <dt>This month</dt>
            <dd>
              US${status.month.costUsd.toFixed(2)}, {status.month.calls} calls, {status.month.unreadable} unreadable
            </dd>
          </dl>
          <div className="flex flex-wrap items-center gap-3">
            <p className="text-sm">
              AI marking and generation: <strong>{status.liveAi ? "on" : "off"}</strong>
            </p>
            <button
              type="button"
              disabled={busy}
              onClick={() => void act(() => api.setLiveAi(!status.liveAi), status.liveAi ? "Switched off." : "Switched on.")}
              className="rounded-sm bg-surface-container-high px-3 py-1 text-sm font-semibold disabled:opacity-50"
            >
              {status.liveAi ? "Switch off" : "Switch on"}
            </button>
          </div>

          <h3 className="font-semibold">Reported questions</h3>
          {status.reported.length === 0 ? (
            <p className="text-sm text-on-surface-variant">Nothing reported.</p>
          ) : (
            <ul className="space-y-3">
              {status.reported.map((q) => (
                <li key={q.id} className="space-y-2 rounded-sm bg-surface-container-lowest p-3 text-sm">
                  <p className="font-mono text-xs text-on-surface-variant">
                    {q.id} · {q.status} · {q.citation} · {q.origin}
                  </p>
                  <p className="font-semibold">{q.text}</p>
                  <ul className="list-disc pl-5">
                    {q.reports.map((r, i) => (
                      <li key={i}>
                        {r.reason}
                        {r.detail ? `: ${r.detail}` : ""}
                      </li>
                    ))}
                  </ul>
                  <details>
                    <summary className="cursor-pointer">Source text</summary>
                    <p className="mt-1 whitespace-pre-wrap">{q.sourceText}</p>
                  </details>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void act(() => api.setQuestionStatus(q.id, "retired"), "Retired.")}
                      className="rounded-sm bg-error px-3 py-1 font-semibold text-white disabled:opacity-50"
                    >
                      Retire
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void act(() => api.setQuestionStatus(q.id, "active"), "Restored.")}
                      className="rounded-sm bg-surface-container-high px-3 py-1 font-semibold disabled:opacity-50"
                    >
                      Keep
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
      {message && (
        <p role="status" className="text-sm text-on-surface-variant">
          {message}
        </p>
      )}
    </section>
  );
}
