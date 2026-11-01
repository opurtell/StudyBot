import { useEffect, useState } from "react";
import { api, type CorpusStatus } from "../lib/api";

const MAX_ROUNDS = 60;

export function CorpusAdmin() {
  const [status, setStatus] = useState<CorpusStatus | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function refresh() {
    try {
      setStatus(await api.corpusStatus());
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Couldn't load the corpus status.");
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function sync() {
    setBusy(true);
    setMessage(null);
    let embedded = 0;
    let removed = 0;
    try {
      for (let round = 0; round < MAX_ROUNDS; round += 1) {
        const result = await api.syncCorpus();
        if (!result.available) {
          setMessage("Vector search isn't configured in this environment.");
          return;
        }
        embedded += result.embedded;
        removed += result.removed;
        setMessage(`Embedded ${embedded}, removed ${removed}, ${result.pending} to go…`);
        if (result.pending === 0 && result.embedded === 0 && result.removed === 0) break;
      }
      setMessage(`Done. Embedded ${embedded} chunks and removed ${removed}.`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Sync failed.");
    } finally {
      setBusy(false);
      await refresh();
    }
  }

  return (
    <section aria-labelledby="corpus-heading" className="space-y-3 rounded-sm bg-surface-container-low p-5">
      <h2 id="corpus-heading" className="font-headline text-xl font-semibold">
        Guideline corpus
      </h2>
      {status ? (
        <dl className="grid grid-cols-2 gap-x-4 gap-y-1 font-mono text-sm">
          <dt>Version</dt>
          <dd>{status.version ?? "not loaded"}</dd>
          <dt>Built</dt>
          <dd>{status.builtAt ?? "–"}</dd>
          <dt>Documents</dt>
          <dd>{status.documents}</dd>
          <dt>Chunks</dt>
          <dd>{status.chunks}</dd>
          <dt>Embedded</dt>
          <dd>{status.embedded}</dd>
          <dt>Waiting</dt>
          <dd>{status.pending + status.retired}</dd>
        </dl>
      ) : (
        <p className="text-sm text-on-surface-variant">Loading…</p>
      )}
      <button
        type="button"
        onClick={sync}
        disabled={busy || !status?.vectorsAvailable}
        className="rounded-sm bg-primary px-4 py-2 text-sm font-semibold text-on-primary disabled:opacity-50"
      >
        {busy ? "Syncing…" : "Sync search index"}
      </button>
      {message && (
        <p role="status" className="text-sm text-on-surface-variant">
          {message}
        </p>
      )}
    </section>
  );
}
