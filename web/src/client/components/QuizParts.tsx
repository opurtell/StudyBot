import { useEffect, useLayoutEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { api, type ReportReason, type Score } from "../lib/api";
import { Attribution, documentPath, SCORE_CLASS, SCORE_LABEL, SELF_LABEL } from "./Feedback";

export const SCORES: Score[] = ["correct", "partial", "incorrect"];

export function Kbd({ children, light = false }: { children: ReactNode; light?: boolean }) {
  return (
    <kbd
      aria-hidden="true"
      className={`ml-2 hidden rounded-sm px-1.5 py-px font-mono text-[11px] font-normal [@media(pointer:fine)]:inline ${light ? "bg-white/20" : "bg-on-surface/10"}`}
    >
      {children}
    </kbd>
  );
}

function clock(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000));
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

export function QuizTimer({ startedAt, stoppedAt }: { startedAt: number; stoppedAt: number | null }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (stoppedAt !== null) return;
    setNow(Date.now());
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [startedAt, stoppedAt]);
  return (
    <span className="font-mono tabular-nums" aria-label="Time on this question">
      {clock((stoppedAt ?? now) - startedAt)}
    </span>
  );
}

function locate(text: string, quote: string | undefined): [number, number] | null {
  const q = quote?.trim();
  if (!q || q.length < 4 || q === text.trim()) return null;
  const exact = text.indexOf(q);
  if (exact >= 0) return [exact, exact + q.length];
  const lower = text.toLowerCase().indexOf(q.toLowerCase());
  return lower >= 0 ? [lower, lower + q.length] : null;
}

export function SourcePanel({
  sourceText,
  sourceQuote,
  citation,
  documentId,
  documentTitle,
  attribution,
}: {
  sourceText: string;
  sourceQuote?: string;
  citation: string;
  documentId: string;
  documentTitle: string;
  attribution?: string;
}) {
  const body = useRef<HTMLDivElement>(null);
  const mark = useRef<HTMLElement>(null);
  const range = locate(sourceText, sourceQuote);

  useLayoutEffect(() => {
    if (body.current && mark.current) body.current.scrollTop = Math.max(0, mark.current.offsetTop - body.current.offsetTop - 12);
  }, [sourceText, sourceQuote]);

  return (
    <section aria-label="From the source" className="flex min-h-40 flex-1 flex-col rounded-sm bg-surface-container-lowest">
      <div className="flex justify-between gap-2 px-4 pt-3 pb-1 text-xs font-medium uppercase tracking-widest text-on-surface-variant">
        <h3>From the source</h3>
        {range && <span className="hidden normal-case tracking-normal sm:inline">Quoted line highlighted</span>}
      </div>
      {sourceQuote && !range && (
        <blockquote className="mx-4 mb-2 border-l-4 border-highlight pl-3 text-sm italic">{sourceQuote}</blockquote>
      )}
      <div ref={body} tabIndex={0} aria-label="Guideline extract" className="min-h-0 flex-1 overflow-auto px-4 pb-3 text-sm leading-relaxed whitespace-pre-wrap">
        {range ? (
          <>
            {sourceText.slice(0, range[0])}
            <mark ref={mark} className="bg-highlight/70 text-on-surface">
              {sourceText.slice(range[0], range[1])}
            </mark>
            {sourceText.slice(range[1])}
          </>
        ) : (
          sourceText
        )}
      </div>
      <p className="flex flex-wrap justify-between gap-2 rounded-b-sm bg-surface-container px-4 py-2 text-xs text-on-surface-variant">
        <span>Ref: {citation}</span>
        <a href={documentPath(documentId)} target="_blank" rel="noopener noreferrer" className="text-primary underline">
          Read {documentTitle}
        </a>
      </p>
      <div className="px-4 pb-2">
        <Attribution documentId={documentId} attribution={attribution} />
      </div>
    </section>
  );
}

function List({ title, items, tone }: { title: string; items: string[]; tone: "good" | "bad" }) {
  if (items.length === 0) return null;
  return (
    <div>
      <h4 className="mb-1 text-xs font-medium uppercase tracking-widest text-on-surface-variant">{title}</h4>
      <ul className="space-y-1 text-sm">
        {items.map((item, i) => (
          <li key={i} className="grid grid-cols-[1rem_1fr] gap-2">
            <span aria-hidden="true" className={tone === "good" ? "text-primary" : "text-error"}>
              {tone === "good" ? "✓" : "✕"}
            </span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function correctionOptions(score: Score): Score[] {
  if (score === "correct") return ["incorrect"];
  if (score === "partial") return ["correct", "incorrect"];
  return ["correct"];
}

export function MarkPanel({
  score,
  corrected,
  summary,
  correctElements,
  missingOrWrong,
  onCorrect,
  disabled,
}: {
  score: Score;
  corrected: Score | null;
  summary: string;
  correctElements: string[];
  missingOrWrong: string[];
  onCorrect: ((score: Score) => void) | null;
  disabled: boolean;
}) {
  const shown = corrected ?? score;
  return (
    <div className="space-y-4">
      <h3 className="sr-only">Assessment</h3>
      <p className="flex flex-wrap items-center gap-3">
        <span className={`inline-block rounded-sm px-2 py-1 text-sm font-semibold ${SCORE_CLASS[shown]}`}>{SCORE_LABEL[shown]}</span>
        <span className="text-xs text-on-surface-variant">{corrected ? "Changed by you" : "Marked by AI"}</span>
      </p>
      {summary && <p className="leading-relaxed">{summary}</p>}
      <List title="What you got right" items={correctElements} tone="good" />
      <List title="Missing or wrong" items={missingOrWrong} tone="bad" />
      {onCorrect &&
        (corrected ? (
          <p role="status" className="text-sm text-on-surface-variant">
            Mark changed to {SCORE_LABEL[corrected]}. Saved to your progress.
          </p>
        ) : (
          <div className="flex flex-wrap items-center gap-1 text-sm text-on-surface-variant">
            <span className="mr-1">Marking wrong?</span>
            {correctionOptions(score).map((option) => (
              <button
                key={option}
                type="button"
                disabled={disabled}
                onClick={() => onCorrect(option)}
                aria-keyshortcuts={String(SCORES.indexOf(option) + 1)}
                className="min-h-9 rounded-sm px-2 font-medium text-on-surface hover:bg-surface-container disabled:opacity-50"
              >
                {option === "correct" ? "I was correct" : option === "partial" ? "I was partly correct" : "I was incorrect"}
                <Kbd>{SCORES.indexOf(option) + 1}</Kbd>
              </button>
            ))}
          </div>
        ))}
    </div>
  );
}

export function SelfMark({ value, onChoose, disabled }: { value: Score | null; onChoose: (score: Score) => void; disabled?: boolean }) {
  return (
    <fieldset className="space-y-2">
      <legend className="text-sm font-semibold">How did you go?</legend>
      <div className="grid grid-cols-3 gap-2">
        {SCORES.map((score, i) => (
          <button
            key={score}
            type="button"
            aria-pressed={value === score}
            aria-keyshortcuts={String(i + 1)}
            disabled={disabled}
            onClick={() => onChoose(score)}
            className={`min-h-11 rounded-sm px-2 text-sm font-semibold disabled:opacity-50 ${value === score ? SCORE_CLASS[score] : "bg-surface-container-high"}`}
          >
            {SELF_LABEL[score]}
            <Kbd light={value === score}>{i + 1}</Kbd>
          </button>
        ))}
      </div>
      {value && (
        <p role="status" className="text-xs text-on-surface-variant">
          Saved to your progress.
        </p>
      )}
    </fieldset>
  );
}

const REASONS: { value: ReportReason; label: string }[] = [
  { value: "incorrect", label: "Clinically wrong" },
  { value: "not_in_source", label: "Answer isn't in the guideline" },
  { value: "out_of_scope", label: "Outside my scope of practice" },
  { value: "unclear", label: "Unclear or badly worded" },
  { value: "other", label: "Something else" },
];

function Dialog({ label, onClose, children, wide = false }: { label: string; onClose: () => void; children: ReactNode; wide?: boolean }) {
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    box.current?.querySelector<HTMLElement>("input, button, textarea")?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopImmediatePropagation();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey, true);
    return () => {
      window.removeEventListener("keydown", onKey, true);
      previous?.focus?.();
    };
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center bg-on-surface/30 sm:items-center" onClick={onClose}>
      <div
        ref={box}
        role="dialog"
        aria-modal="true"
        aria-label={label}
        onClick={(e) => e.stopPropagation()}
        className={`w-full space-y-3 rounded-t-lg bg-surface p-5 pb-[calc(1.25rem+env(safe-area-inset-bottom))] shadow-xl sm:rounded-sm sm:pb-5 ${wide ? "sm:max-w-lg" : "sm:max-w-md"}`}
      >
        {children}
      </div>
    </div>
  );
}

export function ReportDialog({ questionId, onClose, onSent }: { questionId: string; onClose: () => void; onSent: () => void }) {
  const [reason, setReason] = useState<ReportReason | "">("");
  const [detail, setDetail] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLTextAreaElement || e.metaKey || e.ctrlKey || e.altKey) return;
      const n = Number(e.key);
      if (n >= 1 && n <= REASONS.length) {
        e.preventDefault();
        setReason(REASONS[n - 1]!.value);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!reason) return;
    setSending(true);
    setError(null);
    try {
      await api.report(questionId, reason, detail);
      onSent();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't send the report. Try again shortly.");
      setSending(false);
    }
  }

  return (
    <Dialog label="Report a problem" onClose={onClose}>
      <form onSubmit={(e) => void submit(e)} className="space-y-3">
        <fieldset className="space-y-1">
          <legend className="mb-1 font-headline text-xl font-semibold">What's wrong with this question?</legend>
          {REASONS.map((r, i) => (
            <label key={r.value} className={`flex min-h-10 items-center gap-3 rounded-sm px-2 text-sm ${reason === r.value ? "bg-surface-container" : ""}`}>
              <input type="radio" name="reason" value={r.value} checked={reason === r.value} onChange={() => setReason(r.value)} />
              <span className="flex-1">{r.label}</span>
              <Kbd>{i + 1}</Kbd>
            </label>
          ))}
        </fieldset>
        <label className="block text-sm">
          <span className="mb-1 block">Details (optional)</span>
          <textarea
            value={detail}
            onChange={(e) => setDetail(e.target.value)}
            rows={2}
            maxLength={1000}
            className="w-full rounded-sm bg-surface-container-low p-2"
          />
        </label>
        {error && (
          <p role="alert" className="text-sm text-error">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="min-h-10 rounded-sm px-4 text-sm font-semibold hover:bg-surface-container">
            Cancel
            <Kbd>Esc</Kbd>
          </button>
          <button
            type="submit"
            disabled={!reason || sending}
            className="min-h-10 rounded-sm bg-primary px-4 text-sm font-semibold text-on-primary disabled:opacity-50"
          >
            {sending ? "Sending…" : "Send report"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}

const HELP: [string, string][][] = [
  [
    ["Enter", "Mark my answer (guests: reveal the reference)"],
    ["Shift + Enter", "New line"],
    ["⌥R / Alt + R", "Reveal the reference"],
    ["⌥S / Alt + S", "Skip the question"],
  ],
  [
    ["Enter", "Next question"],
    ["1  2  3", "Mark yourself, or correct the AI's mark"],
    ["G", "Open the guideline in a new tab"],
    ["F", "Report a problem"],
  ],
  [
    ["Esc", "End the session (closes a dialog first)"],
    ["?", "Show this list"],
  ],
];
const HELP_TITLES = ["While answering", "After marking or revealing", "Anywhere"];

export function ShortcutHelp({ onClose }: { onClose: () => void }) {
  return (
    <Dialog label="Keyboard shortcuts" onClose={onClose} wide>
      <h2 className="font-headline text-xl font-semibold">Keyboard shortcuts</h2>
      {HELP.map((group, i) => (
        <div key={HELP_TITLES[i]}>
          <h3 className="mb-1 text-xs font-medium uppercase tracking-widest text-on-surface-variant">{HELP_TITLES[i]}</h3>
          <dl className="grid grid-cols-[8rem_1fr] gap-x-3 gap-y-1 text-sm">
            {group.map(([key, what]) => (
              <div key={key + what} className="contents">
                <dt>
                  <kbd className="rounded-sm bg-on-surface/10 px-1.5 py-px font-mono text-xs">{key}</kbd>
                </dt>
                <dd>{what}</dd>
              </div>
            ))}
          </dl>
        </div>
      ))}
      <div className="flex justify-end">
        <button type="button" onClick={onClose} className="min-h-10 rounded-sm bg-surface-container-high px-4 text-sm font-semibold">
          Close
        </button>
      </div>
    </Dialog>
  );
}
