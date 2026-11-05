import type { TopicDocument } from "../../shared/progress";
import type { DocumentKind, QuizFilters, Topic } from "./api";
import type { Preferences } from "./preferences";

export type Mode = "only" | "except";

export interface Selection {
  pools: DocumentKind[];
  mode: Mode;
  picked: string[];
}

export interface PickerDoc extends TopicDocument {
  section: string;
}

export interface PickerGroup {
  key: string;
  label: string;
  kind: DocumentKind;
  docs: PickerDoc[];
}

export const POOLS: { kind: DocumentKind; label: string; noun: string }[] = [
  { kind: "cmg", label: "Guidelines", noun: "guidelines" },
  { kind: "med", label: "Medications", noun: "medications" },
  { kind: "csm", label: "Skills", noun: "skills" },
  { kind: "ref", label: "Pathophysiology and ECGs", noun: "references" },
];

const REFERENCE_SECTION_ORDER = ["Pathophysiology", "ECGs", "Broader pathophysiology"];

export const EVERYTHING: Selection = { pools: POOLS.map((p) => p.kind), mode: "only", picked: [] };

const SECTION_ORDER = [
  "Cardiac",
  "Respiratory",
  "Airway Management",
  "Neurology",
  "Trauma",
  "Medical",
  "Pain Management",
  "Toxicology",
  "Environmental",
  "Obstetric",
  "Behavioural",
  "HAZMAT",
  "Palliative Care",
  "General Care",
];

const SKILL_GROUPS: [string, string][] = [
  ["A", "Airway"],
  ["B", "Breathing"],
  ["C", "Circulation"],
  ["DF", "Drugs and fluids"],
  ["IDH", "Bandaging, splinting and haemorrhage"],
  ["PA", "Patient assessment"],
  ["P", "Patient positioning"],
  ["M", "Miscellaneous"],
];

function skillGroup(doc: PickerDoc): { id: string; label: string } {
  const prefix = /^CSM\.([A-Z]+)\d/.exec(doc.number)?.[1];
  const known = SKILL_GROUPS.find(([code]) => code === prefix);
  return known ? { id: known[0], label: `${known[1]} (${known[0]})` } : { id: doc.section, label: doc.section };
}

function rank(order: string[], id: string): number {
  const i = order.indexOf(id);
  return i === -1 ? order.length : i;
}

export function buildGroups(topics: Topic[]): PickerGroup[] {
  const groups = new Map<string, PickerGroup>();
  for (const topic of topics) {
    for (const d of topic.documents) {
      const doc: PickerDoc = { ...d, section: topic.section };
      const sub =
        doc.kind === "cmg" || doc.kind === "ref"
          ? { id: topic.section, label: topic.section }
          : doc.kind === "med"
            ? { id: "all", label: "All medications" }
            : skillGroup(doc);
      const key = `${doc.kind}:${sub.id}`;
      const group = groups.get(key) ?? { key, label: sub.label, kind: doc.kind, docs: [] };
      group.docs.push(doc);
      groups.set(key, group);
    }
  }
  const order = (g: PickerGroup) => {
    const id = g.key.slice(g.kind.length + 1);
    if (g.kind === "cmg") return rank(SECTION_ORDER, id);
    if (g.kind === "ref") return rank(REFERENCE_SECTION_ORDER, id);
    return g.kind === "csm" ? rank(SKILL_GROUPS.map(([c]) => c), id) : 0;
  };
  const kindRank = (k: DocumentKind) => POOLS.findIndex((p) => p.kind === k);
  const list = [...groups.values()];
  for (const g of list) g.docs.sort((a, b) => a.number.localeCompare(b.number, "en", { numeric: true }));
  return list.sort((a, b) => kindRank(a.kind) - kindRank(b.kind) || order(a) - order(b) || a.label.localeCompare(b.label));
}

export function isOffInSettings(doc: PickerDoc, prefs: Pick<Preferences, "excludedSections" | "excludedDocuments">): boolean {
  return prefs.excludedSections.includes(doc.section) || prefs.excludedDocuments.includes(doc.id);
}

export function togglePool(selection: Selection, kind: DocumentKind): Selection {
  const all = selection.pools.length === POOLS.length;
  if (all) return { ...selection, pools: [kind] };
  const pools = selection.pools.includes(kind) ? selection.pools.filter((k) => k !== kind) : [...selection.pools, kind];
  return { ...selection, pools: pools.length === 0 ? EVERYTHING.pools : POOLS.map((p) => p.kind).filter((k) => pools.includes(k)) };
}

export interface Resolved {
  filters: Pick<QuizFilters, "kinds" | "documentIds" | "excludeDocumentIds">;
  useSettings: boolean;
  inPlay: PickerDoc[];
  picked: PickerDoc[];
  questions: number;
}

export function resolveSelection(selection: Selection, groups: PickerGroup[], prefs: Pick<Preferences, "excludedSections" | "excludedDocuments">): Resolved {
  const all = selection.pools.length === POOLS.length;
  const kinds = all ? null : selection.pools;
  const docs = groups.filter((g) => selection.pools.includes(g.kind)).flatMap((g) => g.docs);
  const pickedIds = new Set(selection.picked);
  const picked = docs.filter((d) => pickedIds.has(d.id));
  const usable = (d: PickerDoc) => !isOffInSettings(d, prefs);
  let inPlay: PickerDoc[];
  let filters: Resolved["filters"];
  let useSettings = true;

  if (picked.length === 0) {
    inPlay = docs.filter(usable);
    filters = { kinds, documentIds: null, excludeDocumentIds: [] };
  } else if (selection.mode === "only") {
    const poolsWithPicks = new Set(picked.map((d) => d.kind));
    inPlay = docs.filter((d) => (poolsWithPicks.has(d.kind) ? pickedIds.has(d.id) : usable(d)));
    filters = { kinds, documentIds: inPlay.map((d) => d.id), excludeDocumentIds: [] };
    useSettings = false;
  } else {
    inPlay = docs.filter((d) => !pickedIds.has(d.id) && usable(d));
    filters = { kinds, documentIds: null, excludeDocumentIds: picked.map((d) => d.id) };
  }
  return { filters, useSettings, inPlay, picked, questions: inPlay.reduce((n, d) => n + d.questions, 0) };
}

export function poolsLabel(selection: Selection): string {
  if (selection.pools.length === POOLS.length) return "Everything";
  return POOLS.filter((p) => selection.pools.includes(p.kind))
    .map((p) => p.label)
    .join(" + ");
}

export function selectionFromLink(groups: PickerGroup[], params: { document: string | null; section: string | null }): Selection | null {
  if (params.document) {
    const doc = groups.flatMap((g) => g.docs).find((d) => d.id === params.document);
    return doc ? { pools: [doc.kind], mode: "only", picked: [doc.id] } : null;
  }
  if (params.section) {
    const docs = groups.flatMap((g) => g.docs).filter((d) => d.section === params.section);
    if (docs.length === 0) return null;
    const pools = POOLS.map((p) => p.kind).filter((k) => docs.some((d) => d.kind === k));
    return { pools, mode: "only", picked: docs.map((d) => d.id) };
  }
  return null;
}
