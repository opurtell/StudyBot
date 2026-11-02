import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { CorpusAdmin } from "../components/CorpusAdmin";
import { documentLabel } from "../components/DocumentList";
import { QuestionAdmin } from "../components/QuestionAdmin";
import { ScopePicker } from "../components/ScopePicker";
import { api } from "../lib/api";
import { clearGuestAttempts } from "../lib/guestProgress";
import { usePreferences } from "../lib/preferences";
import { useScopeChoice } from "../lib/scopeView";
import { useSession } from "../lib/session";
import { useLoad } from "../lib/useLoad";

function Panel({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section aria-labelledby={id} className="space-y-3 rounded-sm bg-surface-container-low p-4 sm:p-5">
      <h2 id={id} className="font-headline text-xl font-semibold">
        {title}
      </h2>
      {children}
    </section>
  );
}

function toggle(list: string[], value: string, on: boolean): string[] {
  return on ? [...new Set([...list, value])] : list.filter((v) => v !== value);
}

function ExcludedTopics() {
  const { prefs, update } = usePreferences();
  const { data, error, loading } = useLoad(() => api.topics("icp_pacer"), []);
  const excludedCount = prefs.excludedSections.length + prefs.excludedDocuments.length;

  return (
    <Panel id="excluded-heading" title="Excluded topics">
      <p className="text-sm text-on-surface-variant">
        Leave topics out of quizzes. Picking a guideline on the quiz page still overrides this.
        {excludedCount > 0 && ` ${excludedCount} excluded.`}
      </p>
      {loading && <p className="text-sm text-on-surface-variant">Loading…</p>}
      {error && (
        <p role="alert" className="text-sm text-error">
          {error}
        </p>
      )}
      <ul className="space-y-1">
        {data?.topics.map((topic) => {
          const sectionOff = prefs.excludedSections.includes(topic.section);
          return (
            <li key={topic.section} className="rounded-sm bg-surface-container-lowest px-3 py-2">
              <label className="flex min-h-11 items-center gap-3">
                <input
                  type="checkbox"
                  checked={sectionOff}
                  onChange={(e) => update({ ...prefs, excludedSections: toggle(prefs.excludedSections, topic.section, e.target.checked) })}
                  className="h-5 w-5"
                />
                <span className="font-medium">Exclude {topic.section}</span>
              </label>
              {!sectionOff && (
                <details className="pb-1 pl-8">
                  <summary className="cursor-pointer py-1 text-sm text-on-surface-variant">Exclude single guidelines</summary>
                  <ul className="mt-1 space-y-1">
                    {topic.documents.map((doc) => (
                      <li key={doc.id}>
                        <label className="flex min-h-9 items-center gap-3 text-sm">
                          <input
                            type="checkbox"
                            checked={prefs.excludedDocuments.includes(doc.id)}
                            onChange={(e) =>
                              update({ ...prefs, excludedDocuments: toggle(prefs.excludedDocuments, doc.id, e.target.checked) })
                            }
                            className="h-4 w-4"
                          />
                          {documentLabel(doc)} {doc.title}
                        </label>
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}

function ResetProgress() {
  const { me } = useSession();
  const [confirming, setConfirming] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function reset() {
    setError(null);
    try {
      if (me?.signedIn) await api.resetProgress();
      else clearGuestAttempts();
      setDone(true);
      setConfirming(false);
    } catch {
      setError("Couldn't reset your progress. Try again shortly.");
    }
  }

  return (
    <Panel id="reset-heading" title="Reset progress">
      <p className="text-sm text-on-surface-variant">
        Clears your answer history, mastery and streak{me?.signedIn ? "" : " in this browser"}. Library questions you've seen
        will come round again.
      </p>
      {done && (
        <p role="status" className="text-sm">
          Your progress has been reset.
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm text-error">
          {error}
        </p>
      )}
      {confirming ? (
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={() => void reset()} className="min-h-11 rounded-sm bg-error px-4 py-2 text-sm font-semibold text-white">
            Yes, reset my progress
          </button>
          <button type="button" onClick={() => setConfirming(false)} className="min-h-11 rounded-sm px-4 py-2 text-sm font-semibold">
            Cancel
          </button>
        </div>
      ) : (
        <button type="button" onClick={() => setConfirming(true)} className="min-h-11 rounded-sm px-4 py-2 text-sm font-semibold text-error">
          Reset progress…
        </button>
      )}
    </Panel>
  );
}

function AccountPanel() {
  const { me, signOut, refresh } = useSession();
  const navigate = useNavigate();
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!me?.signedIn) return null;

  async function onSignOut() {
    await signOut();
    navigate("/");
  }

  async function onDelete() {
    try {
      await api.deleteAccount();
      await refresh();
      navigate("/");
    } catch {
      setError("Couldn't delete your account. Try again shortly.");
    }
  }

  return (
    <>
      <Panel id="account-heading" title="Account">
        <p className="text-sm">
          Signed in as <strong>{me.email}</strong>
        </p>
        <button type="button" onClick={() => void onSignOut()} className="min-h-11 rounded-sm bg-surface-container-high px-4 py-2 text-sm font-semibold">
          Sign out
        </button>
      </Panel>

      {me.isAdmin && <QuestionAdmin />}
      {me.isAdmin && <CorpusAdmin />}

      <Panel id="delete-heading" title="Delete account">
        <p className="text-sm text-on-surface-variant">
          This removes your account, your settings, your study history and your sign-in sessions. It can't be undone.
        </p>
        {error && (
          <p role="alert" className="text-sm text-error">
            {error}
          </p>
        )}
        {confirming ? (
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={() => void onDelete()} className="min-h-11 rounded-sm bg-error px-4 py-2 text-sm font-semibold text-white">
              Yes, delete my account
            </button>
            <button type="button" onClick={() => setConfirming(false)} className="min-h-11 rounded-sm px-4 py-2 text-sm font-semibold">
              Cancel
            </button>
          </div>
        ) : (
          <button type="button" onClick={() => setConfirming(true)} className="min-h-11 rounded-sm px-4 py-2 text-sm font-semibold text-error">
            Delete account…
          </button>
        )}
      </Panel>
    </>
  );
}

export function Settings() {
  const { me, loading } = useSession();
  const { syncError } = usePreferences();
  const [choice, setChoice] = useScopeChoice();
  if (loading) return <p className="text-on-surface-variant">Loading…</p>;

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="font-headline text-3xl font-semibold">Settings</h1>
        <p className="text-on-surface-variant">
          {me?.signedIn ? "Saved to your account, so they follow you to any device." : "Saved in this browser."}
        </p>
      </header>
      {syncError && (
        <p role="alert" className="rounded-sm bg-error-container p-3 text-sm text-error">
          {syncError}
        </p>
      )}

      <Panel id="scope-heading" title="Scope of practice">
        <p className="text-sm text-on-surface-variant">
          Sets which guideline content and questions you see. AP hides ICP-only content; PACER adds PACER content.
        </p>
        <ScopePicker choice={choice} onChange={setChoice} legend="Your qualification" label="I am" />
      </Panel>

      <ExcludedTopics />
      <ResetProgress />

      {me?.signedIn ? (
        <AccountPanel />
      ) : (
        <Panel id="signin-heading" title="Account">
          <p className="text-sm text-on-surface-variant">
            Sign in to keep your settings and progress on your account, and to use AI marking.
          </p>
          <Link to="/sign-in" className="inline-block min-h-11 rounded-sm bg-primary px-4 py-2 text-sm font-semibold text-on-primary">
            Sign in with Google
          </Link>
        </Panel>
      )}
    </div>
  );
}
