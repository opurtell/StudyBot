import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router";
import type { Preferences } from "../lib/preferences";
import {
  EVERYTHING,
  isOffInSettings,
  POOLS,
  poolsLabel,
  togglePool,
  type PickerDoc,
  type PickerGroup,
  type Resolved,
  type Selection,
} from "../lib/quizSelection";
import { documentLabel } from "./DocumentList";

function CheckIcon({ className = "" }: { className?: string }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M5 12.5l4.5 4.5L19 7.5" />
    </svg>
  );
}

function plural(n: number, one: string, many = `${one}s`) {
  return `${n} ${n === 1 ? one : many}`;
}

export function TopicPicker({
  groups,
  allGroups,
  loading,
  error,
  selection,
  onChange,
  prefs,
  scopeName,
  controls,
  details,
  start,
}: {
  groups: PickerGroup[];
  allGroups: PickerGroup[];
  loading: boolean;
  error: string | null;
  selection: Selection;
  onChange: (next: Selection) => void;
  prefs: Pick<Preferences, "excludedSections" | "excludedDocuments">;
  scopeName: string;
  controls: ReactNode;
  details: { label: string; value: string }[];
  start: { resolved: Resolved; button: ReactNode };
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState<Set<string>>(() => new Set());
  const opened = useRef(false);
  const only = selection.mode === "only";
  const allOn = selection.pools.length === POOLS.length;
  const picked = useMemo(() => new Set(selection.picked), [selection.picked]);
  const q = query.trim().toLowerCase();

  useEffect(() => {
    if (opened.current || groups.length === 0) return;
    opened.current = true;
    const withPicks = groups.filter((g) => g.docs.some((d) => picked.has(d.id))).map((g) => g.key);
    if (withPicks.length) setOpen(new Set(withPicks));
  }, [groups, picked]);

  const counts = (kind: string) => groups.filter((g) => g.kind === kind).reduce((n, g) => n + g.docs.length, 0);
  const total = POOLS.reduce((n, p) => n + counts(p.kind), 0);

  const setPicked = (ids: string[]) => onChange({ ...selection, picked: ids });
  const toggleDoc = (id: string) => setPicked(picked.has(id) ? selection.picked.filter((p) => p !== id) : [...selection.picked, id]);

  const pools = POOLS.filter((p) => selection.pools.includes(p.kind)).map((pool) => {
    const poolGroups = groups
      .filter((g) => g.kind === pool.kind)
      .map((g) => {
        const shown = q ? g.docs.filter((d) => `${documentLabel(d)} ${d.title}`.toLowerCase().includes(q)) : g.docs;
        const eligible = only ? g.docs : g.docs.filter((d) => !isOffInSettings(d, prefs));
        const n = eligible.filter((d) => picked.has(d.id)).length;
        const hidden = (allGroups.find((a) => a.key === g.key)?.docs.length ?? g.docs.length) - g.docs.length;
        return { group: g, shown, eligible, n, hidden, isOpen: q ? shown.length > 0 : open.has(g.key) };
      })
      .filter((g) => !q || g.shown.length > 0);
    const picks = groups.filter((g) => g.kind === pool.kind).reduce((n, g) => n + g.docs.filter((d) => picked.has(d.id)).length, 0);
    return { pool, groups: poolGroups, picks };
  });

  const offNames = [
    ...prefs.excludedSections,
    ...groups
      .flatMap((g) => g.docs)
      .filter((d) => prefs.excludedDocuments.includes(d.id) && !prefs.excludedSections.includes(d.section))
      .map((d) => `${documentLabel(d)} ${d.title}`),
  ];

  const { resolved } = start;
  const lines: { label: string; value: string; sub?: boolean }[] = [];
  for (const { pool } of pools) {
    const poolDocs = groups.filter((g) => g.kind === pool.kind).flatMap((g) => g.docs);
    const inPlay = resolved.inPlay.filter((d) => d.kind === pool.kind).length;
    const poolPicks = resolved.picked.filter((d) => d.kind === pool.kind);
    if (poolPicks.length === 0) {
      lines.push({ label: pool.label, value: `all ${inPlay}` });
      continue;
    }
    lines.push({ label: pool.label, value: `${inPlay} of ${poolDocs.length}` });
    for (const g of groups.filter((g) => g.kind === pool.kind)) {
      const gp = g.docs.filter((d) => picked.has(d.id)).length;
      if (!gp) continue;
      const allOf = gp === g.docs.length;
      lines.push({ label: g.label, value: only ? (allOf ? `all ${gp}` : `${gp} of ${g.docs.length}`) : allOf ? "all left out" : `${gp} left out`, sub: true });
    }
  }
  const pickCount = resolved.picked.length;
  const modeLabel = pickCount === 0 ? "Nothing narrowed" : only ? "Only the ticked topics" : "Everything except the ticked topics";
  const summary = `${resolved.questions} ${resolved.questions === 1 ? "question" : "questions"} in play${pickCount ? ` · ${pickCount} ${only ? "picked" : "left out"}` : ""}`;

  return (
    <div className="lg:relative lg:left-1/2 lg:w-[min(72rem,calc(100vw-4rem))] lg:-translate-x-1/2">
      <div className="lg:grid lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-start lg:gap-10">
        <div className="space-y-8 pb-4">
          {controls}

          <section aria-labelledby="pools-heading" className="space-y-3">
            <div className="flex flex-wrap items-baseline gap-x-3">
              <span className="font-mono text-sm text-primary" aria-hidden="true">
                01
              </span>
              <h2 id="pools-heading" className="font-headline text-2xl font-semibold">
                Draw questions from
              </h2>
              <span className="text-sm text-on-surface-variant">Pick one or more</span>
            </div>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 sm:gap-3">
              {[
                { key: "all", label: "Everything", sub: `All ${plural(total, "document")}`, pressed: allOn, tone: allOn ? "on" : "off", click: () => onChange({ ...selection, pools: EVERYTHING.pools }) },
                ...POOLS.map((p) => {
                  const on = selection.pools.includes(p.kind);
                  return { key: p.kind, label: p.label, sub: `${counts(p.kind)} ${p.noun}`, pressed: on, tone: allOn ? "inc" : on ? "on" : "off", click: () => onChange(togglePool(selection, p.kind)) };
                }),
              ].map((t) => (
                <button
                  key={t.key}
                  type="button"
                  aria-pressed={t.pressed}
                  onClick={t.click}
                  className={`relative flex min-h-24 flex-col justify-between gap-3 rounded-sm p-3 text-left sm:min-h-28 sm:p-4 ${
                    t.tone === "on" ? "bg-primary text-on-primary" : t.tone === "inc" ? "bg-primary-fixed text-on-surface" : "bg-surface-container-lowest hover:bg-surface-container"
                  }`}
                >
                  <span className="pr-6 font-headline text-xl font-semibold leading-tight sm:text-2xl">{t.label}</span>{" "}
                  <span className="font-mono text-xs">{t.sub}</span>
                  {t.tone !== "off" && (
                    <span className="absolute right-3 top-3 flex h-5 w-5 items-center justify-center rounded-full bg-highlight text-on-highlight">
                      <CheckIcon className="h-3 w-3" />
                    </span>
                  )}
                </button>
              ))}
            </div>
          </section>

          <section aria-labelledby="narrow-heading" className="space-y-3">
            <div className="flex flex-wrap items-baseline justify-between gap-x-3">
              <div className="flex flex-wrap items-baseline gap-x-3">
                <span className="font-mono text-sm text-primary" aria-hidden="true">
                  02
                </span>
                <h2 id="narrow-heading" className="font-headline text-2xl font-semibold">
                  Narrow it down
                </h2>
                <span className="text-sm text-on-surface-variant">Optional</span>
              </div>
              {pickCount > 0 && (
                <button type="button" onClick={() => setPicked([])} className="min-h-10 text-sm font-medium text-primary underline">
                  Clear ticks
                </button>
              )}
            </div>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div role="group" aria-label="Narrowing mode" className="grid grid-cols-2 rounded-sm bg-surface-container-high p-1 sm:inline-grid">
                {(
                  [
                    ["only", "Only these"],
                    ["except", "Everything except these"],
                  ] as const
                ).map(([mode, label]) => (
                  <button
                    key={mode}
                    type="button"
                    aria-pressed={selection.mode === mode}
                    onClick={() => selection.mode !== mode && onChange({ ...selection, mode, picked: [] })}
                    className={`min-h-10 rounded-sm px-3 text-sm font-medium ${selection.mode === mode ? "bg-surface-container-lowest text-on-surface shadow-sm" : "text-on-surface-variant"}`}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <label className="flex min-h-11 items-center gap-2 rounded-sm bg-surface-container-lowest px-3 sm:w-80">
                <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" className="h-4 w-4 text-on-surface-variant">
                  <circle cx="11" cy="11" r="7" />
                  <path d="M20 20l-4-4" />
                </svg>
                <span className="sr-only">Search topics</span>
                <input
                  type="search"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search guidelines, medications, skills"
                  className="min-h-10 flex-1 bg-transparent text-sm"
                />
              </label>
            </div>
            <p className="text-sm text-on-surface-variant">
              {only ? "Tick what you want. A pool with nothing ticked stays whole." : "Tick what to leave out. Everything else in your pools stays in."}
            </p>

            {loading && <p className="text-sm text-on-surface-variant">Loading topics…</p>}
            {error && (
              <p role="alert" className="text-sm text-error">
                {error} You can still start a quiz on the pools above.
              </p>
            )}
            {q && pools.every((p) => p.groups.length === 0) && (
              <p className="rounded-sm bg-surface-container-low p-4 text-sm text-on-surface-variant">Nothing matches that search in the pools you picked.</p>
            )}

            {pools
              .filter((p) => p.groups.length > 0)
              .map(({ pool, groups: poolGroups, picks }) => (
                <div key={pool.kind} className="space-y-1.5 pt-2">
                  <div className="flex items-baseline justify-between px-0.5">
                    <h3 className="text-xs font-semibold uppercase tracking-widest text-primary sm:font-headline sm:text-xl sm:normal-case sm:tracking-normal">{pool.label}</h3>
                    <span className="font-mono text-xs text-on-surface-variant">
                      {picks ? `${picks} ${only ? "picked" : "left out"}` : only ? "nothing ticked · whole pool" : "nothing left out"}
                    </span>
                  </div>
                  {poolGroups.map(({ group, shown, eligible, n, hidden, isOpen }) => {
                    const isAll = n > 0 && n === eligible.length;
                    const isSome = n > 0 && !isAll;
                    const sectionOff = prefs.excludedSections.includes(group.docs[0]?.section ?? "") && group.kind === "cmg";
                    const count = n > 0 ? `${n} of ${eligible.length} ${only ? "picked" : "left out"}` : sectionOff ? "Off in Settings" : plural(group.docs.length, "document");
                    return (
                      <div key={group.key} className="rounded-sm bg-surface-container-low">
                        <div className="flex items-center">
                          <label className="flex h-12 w-12 shrink-0 cursor-pointer items-center justify-center">
                            <span className="sr-only">
                              {isAll ? "Untick all of" : only ? "Pick all of" : "Leave out all of"} {group.label}
                            </span>
                            <input
                              type="checkbox"
                              checked={isAll}
                              ref={(el) => {
                                if (el) el.indeterminate = isSome;
                              }}
                              disabled={eligible.length === 0}
                              onChange={() => {
                                const ids = new Set(selection.picked);
                                for (const d of eligible) {
                                  if (isAll) ids.delete(d.id);
                                  else ids.add(d.id);
                                }
                                setPicked([...ids]);
                              }}
                              className={`h-5 w-5 ${only ? "accent-primary" : "accent-error"}`}
                            />
                          </label>
                          <button
                            type="button"
                            aria-expanded={isOpen}
                            onClick={() =>
                              setOpen((prev) => {
                                const next = new Set(prev);
                                if (next.has(group.key)) next.delete(group.key);
                                else next.add(group.key);
                                return next;
                              })
                            }
                            className="flex min-h-12 min-w-0 flex-1 items-center gap-3 pr-3 text-left"
                          >
                            <span className="min-w-0 flex-1">
                              <span className="block font-semibold leading-snug">{group.label}</span>
                              <span className="block font-mono text-xs text-on-surface-variant sm:hidden">{count}</span>
                            </span>
                            <span className="hidden font-mono text-xs text-on-surface-variant sm:inline">{count}</span>
                            <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={`h-4 w-4 shrink-0 text-on-surface-variant transition-transform ${isOpen ? "rotate-180" : ""}`}>
                              <path d="M6 9l6 6 6-6" />
                            </svg>
                          </button>
                        </div>
                        {isOpen && (
                          <div className="space-y-2 px-2 pb-3 sm:pl-12 sm:pr-3">
                            <ul className="grid gap-1.5 sm:grid-cols-2 lg:grid-cols-3">
                              {shown.map((doc) => (
                                <DocumentChoice key={doc.id} doc={doc} only={only} picked={picked.has(doc.id)} off={isOffInSettings(doc, prefs)} onToggle={() => toggleDoc(doc.id)} />
                              ))}
                            </ul>
                            {hidden > 0 && (
                              <p className="text-xs text-on-surface-variant">
                                {plural(hidden, "document")} hidden by your scope ({scopeName})
                              </p>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              ))}
          </section>
        </div>

        <aside
          aria-label="Your session"
          className="sticky bottom-[calc(4rem+env(safe-area-inset-bottom))] z-10 -mx-4 bg-surface-container-lowest px-4 py-3 shadow-[0_-10px_24px_rgba(27,28,24,0.06)] sm:bottom-0 lg:top-20 lg:mx-0 lg:space-y-4 lg:p-6 lg:shadow-[0_12px_32px_rgba(27,28,24,0.05)]"
        >
          <p className="hidden text-xs font-medium uppercase tracking-widest text-on-surface-variant lg:block">Your session</p>
          <div className="flex items-center gap-3 lg:block lg:space-y-4">
            <div className="min-w-0 flex-1 lg:space-y-1">
              <p className="truncate font-headline text-lg font-semibold text-primary lg:overflow-visible lg:whitespace-normal lg:text-3xl lg:leading-tight">{poolsLabel(selection)}</p>
              <p className="text-xs text-on-surface-variant lg:hidden">{summary}</p>
              <p className="hidden text-sm text-on-surface-variant lg:block">{modeLabel}</p>
            </div>
            <dl className="hidden space-y-1.5 text-sm lg:block">
              {lines.map((l) => (
                <div key={`${l.sub ? "sub" : "pool"}-${l.label}`} className={`flex justify-between gap-3 ${l.sub ? "pl-3.5" : ""}`}>
                  <dt className={l.sub ? "" : "font-semibold"}>{l.label}</dt>
                  <dd className="text-right font-mono text-xs leading-5 text-on-surface-variant">{l.value}</dd>
                </div>
              ))}
            </dl>
            {offNames.length > 0 && (
              <p className="hidden rounded-sm bg-surface-container-low p-3 text-xs leading-relaxed text-on-surface-variant lg:block">
                <span className="font-semibold text-on-surface">Excluded in Settings:</span> {offNames.join(", ")}.{" "}
                <Link to="/settings" className="underline">
                  Change
                </Link>
              </p>
            )}
            <dl className="hidden space-y-1 text-sm lg:block">
              {details.map((d) => (
                <div key={d.label} className="flex justify-between">
                  <dt className="text-on-surface-variant">{d.label}</dt>
                  <dd className="font-medium">{d.value}</dd>
                </div>
              ))}
            </dl>
            <p className="hidden items-baseline gap-2 lg:flex">
              <span className="font-headline text-4xl font-semibold">{resolved.questions}</span>
              <span className="text-sm text-on-surface-variant">{resolved.questions === 1 ? "question" : "questions"} in play</span>
            </p>
            <div className="shrink-0 lg:space-y-2">
              {start.button}
              {(pickCount > 0 || !allOn) && (
                <button type="button" onClick={() => onChange(EVERYTHING)} className="hidden min-h-10 w-full text-sm font-medium text-primary lg:block">
                  Reset to everything
                </button>
              )}
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

function DocumentChoice({ doc, only, picked, off, onToggle }: { doc: PickerDoc; only: boolean; picked: boolean; off: boolean; onToggle: () => void }) {
  const locked = !only && off;
  const isIn = only && picked;
  const isOut = (!only && picked) || locked;
  const tone = isIn ? "bg-highlight text-on-highlight" : isOut ? "bg-surface-container-high text-on-surface-variant" : off ? "bg-surface-container text-on-surface-variant" : "bg-surface-container-lowest";
  return (
    <li>
      <label className={`flex h-full min-h-12 cursor-pointer items-start gap-3 rounded-sm p-2.5 ${tone} ${locked ? "cursor-not-allowed" : ""}`}>
        <input
          type="checkbox"
          checked={picked || locked}
          disabled={locked}
          onChange={onToggle}
          className={`mt-0.5 h-4 w-4 shrink-0 ${only ? "accent-primary" : "accent-error"}`}
        />
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-x-2 font-mono text-xs">
            {documentLabel(doc)}
            {off && <span className="bg-on-surface/10 px-1.5 text-[0.65rem] uppercase tracking-wide">Off in Settings</span>}
          </span>
          <span className={`block text-sm font-medium leading-snug ${isOut ? "line-through" : ""}`}>{doc.title}</span>
        </span>
      </label>
    </li>
  );
}
