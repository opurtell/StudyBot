import { useMemo, useState } from "react";
import { Link } from "react-router";
import type { DocumentSummary } from "../lib/api";
import { ScopeBadge } from "./ScopeBadge";

export function documentLabel(doc: Pick<DocumentSummary, "kind" | "number">): string {
  if (doc.kind === "med") return `MED ${doc.number}`;
  if (doc.kind === "csm") return doc.number;
  return `CMG ${doc.number}`;
}

function group(items: DocumentSummary[]): [string, DocumentSummary[]][] {
  const sections = new Map<string, DocumentSummary[]>();
  for (const item of items) {
    const list = sections.get(item.section) ?? [];
    list.push(item);
    sections.set(item.section, list);
  }
  return [...sections.entries()];
}

export function DocumentList({
  items,
  basePath,
  filterLabel,
  grouped = true,
}: {
  items: DocumentSummary[];
  basePath: string;
  filterLabel: string;
  grouped?: boolean;
}) {
  const [query, setQuery] = useState("");
  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter((i) => `${documentLabel(i)} ${i.title} ${i.section}`.toLowerCase().includes(q));
  }, [items, query]);

  const sections = grouped ? group(shown) : [["", shown] as [string, DocumentSummary[]]];

  return (
    <div className="space-y-6">
      <label className="block max-w-sm">
        <span className="text-xs font-medium uppercase tracking-widest text-on-surface-variant">{filterLabel}</span>
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="mt-1 w-full border-0 border-b-2 border-outline-variant bg-transparent px-0 py-2 focus:border-primary focus:ring-0"
        />
      </label>
      {shown.length === 0 && <p className="text-on-surface-variant">Nothing matches “{query}”.</p>}
      {sections.map(([section, docs]) => (
        <section key={section || "all"} aria-label={section || undefined} className="space-y-2">
          {section && <h2 className="font-headline text-xl font-semibold">{section}</h2>}
          <ul className="space-y-1">
            {docs.map((doc) => (
              <li key={doc.id}>
                <Link
                  to={`${basePath}/${encodeURIComponent(doc.id)}`}
                  className="flex flex-wrap items-baseline gap-x-3 gap-y-1 rounded-sm bg-surface-container-lowest px-3 py-2 hover:bg-surface-container"
                >
                  <span className="font-mono text-xs text-on-surface-variant">{documentLabel(doc)}</span>
                  <span className="font-medium">{doc.title}</span>
                  <ScopeBadge scope={doc.scope} />
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
