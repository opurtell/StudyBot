import Markdown, { type Components } from "react-markdown";
import { Link } from "react-router";
import type { CorpusView, DocumentDetail } from "../lib/api";
import { useScopeChoice, viewFor } from "../lib/scopeView";
import { useLoad } from "../lib/useLoad";
import { documentLabel } from "./DocumentList";
import { ScopeBadge } from "./ScopeBadge";
import { ScopePicker } from "./ScopePicker";

const markdownComponents: Components = {
  h1: ({ children }) => <h2>{children}</h2>,
  a: ({ children, href }) => (
    <a href={href} rel="noopener noreferrer" target="_blank">
      {children}
    </a>
  ),
  img: () => null,
};

const HEADING = /^(#{1,6})(\s+.*)$/;

export function prepareMarkdown(markdown: string, title: string): string {
  const lines = markdown.split("\n");
  if (lines[0]?.replace(/^#\s+/, "").trim() === title.trim()) lines.shift();
  const levels = [...new Set(lines.flatMap((l) => HEADING.exec(l)?.[1]?.length ?? []))].sort((a, b) => a - b);
  const rank = new Map(levels.map((level, i) => [level, Math.min(i + 2, 6)]));
  return lines
    .map((line) => {
      const match = HEADING.exec(line);
      if (!match?.[1]) return line;
      return `${"#".repeat(rank.get(match[1].length) ?? 6)}${match[2]}`;
    })
    .join("\n");
}

function emptyMessage(doc: DocumentDetail): string {
  if (doc.scope === "icp") return "This is ICP only, so it isn't in AP scope. Choose ICP or Everything to read it.";
  if (doc.scope === "pacer") return "This is PACER only. Tick PACER or choose Everything to read it.";
  return "Nothing in this guideline is in the chosen scope.";
}

export function DocumentView({
  id,
  load,
  backTo,
  backLabel,
}: {
  id: string;
  load: (id: string, view: CorpusView) => Promise<DocumentDetail>;
  backTo: string;
  backLabel: string;
}) {
  const [choice, setChoice] = useScopeChoice();
  const view = viewFor(choice);
  const { data: doc, error, loading } = useLoad(() => load(id, view), [id, view]);

  return (
    <article className="space-y-6">
      <Link to={backTo} className="text-sm font-medium text-primary underline">
        ← {backLabel}
      </Link>

      {error && (
        <p role="alert" className="rounded-sm bg-error-container p-3 text-sm text-error">
          {error}
        </p>
      )}

      {doc && (
        <header className="space-y-2">
          <p className="font-mono text-xs uppercase tracking-widest text-on-surface-variant">
            ACTAS {documentLabel(doc)} · {doc.section}
          </p>
          <h1 className="font-headline text-3xl font-semibold leading-tight">{doc.title}</h1>
          <ScopeBadge scope={doc.scope} />
        </header>
      )}

      <ScopePicker choice={choice} onChange={setChoice} />

      {loading && !doc && <p className="text-on-surface-variant">Loading…</p>}

      {doc &&
        (doc.markdown.trim() ? (
          <div className="guideline-body" aria-busy={loading}>
            <Markdown components={markdownComponents} skipHtml>
              {prepareMarkdown(doc.markdown, doc.title)}
            </Markdown>
          </div>
        ) : (
          <p className="rounded-sm bg-surface-container-low p-4 text-on-surface-variant">{emptyMessage(doc)}</p>
        ))}

      {doc && (
        <footer className="space-y-1 text-xs text-on-surface-variant">
          <p>
            Source: {doc.attribution},{" "}
            <a className="underline" href={doc.sourceUrl} rel="noopener noreferrer" target="_blank">
              {new URL(doc.sourceUrl).host}
            </a>
            {doc.versionDate ? `. Version ${doc.versionDate}.` : "."}
          </p>
          <p>Check the current CMG before relying on anything here.</p>
        </footer>
      )}
    </article>
  );
}
