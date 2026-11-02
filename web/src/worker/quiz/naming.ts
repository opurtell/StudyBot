import { CORPUS_SERVICE } from "../corpus/repo";

/**
 * Users know "the Electric Shock guideline", not "CMG 31" (Oscar's bank review, 2026-11-02), so generated questions
 * get the title added wherever they name a guideline, skill or medicine guideline only by its code. Mirrors
 * `name_documents` in src/python/web_corpus/questions.py; both run the cases in test/fixtures/naming-cases.json.
 */

export type DocumentTitles = Map<string, { kind: "cmg" | "med" | "csm"; title: string }>;

const DOC_CODE =
  /(\b[Tt]he\s+)?(ACTAS\s+)?(?:(CMG|MED)\s*(\d{1,2}[A-Za-z]?)|(CSM\.[A-Z]{1,2}\d{2}))(?!\.\d|\w)/g;
const NOUN = { cmg: "guideline", med: "medicine guideline", csm: "skill" } as const;
const TITLE_WINDOW = 80;

export function documentTitles(rows: { kind: string; number: string; title: string }[]): DocumentTitles {
  const titles: DocumentTitles = new Map();
  for (const row of rows) {
    if (row.kind === "csm" && row.number.toUpperCase().startsWith("CSM.")) {
      titles.set(row.number.toUpperCase(), { kind: "csm", title: row.title });
    } else if (row.kind === "cmg" || row.kind === "med") {
      titles.set(`${row.kind.toUpperCase()} ${row.number.toUpperCase()}`, { kind: row.kind, title: row.title });
    }
  }
  return titles;
}

export async function loadDocumentTitles(db: D1Database): Promise<DocumentTitles> {
  const { results } = await db
    .prepare("SELECT kind, number, title FROM corpus_documents WHERE service = ?1")
    .bind(CORPUS_SERVICE)
    .all<{ kind: string; number: string; title: string }>();
  return documentTitles(results);
}

export function nameDocuments(text: string, titles: DocumentTitles): string {
  return text.replace(
    DOC_CODE,
    (match: string, the: string | undefined, actas: string | undefined, kind: string | undefined,
      num: string | undefined, csm: string | undefined, offset: number) => {
      let code: string;
      if (csm) {
        code = csm.toUpperCase();
      } else {
        let n = num!.toUpperCase();
        if (kind === "MED" && n.length === 1) n = `0${n}`;
        code = `${kind} ${n}`;
      }
      const found = titles.get(code);
      if (!found) return match;
      const nearby = text.slice(Math.max(0, offset - TITLE_WINDOW), offset + match.length + TITLE_WINDOW).toLowerCase();
      if (nearby.includes(found.title.toLowerCase())) return match;
      let article = the;
      if (article === undefined) {
        const before = text.slice(0, offset).trimEnd();
        article = !before || ".?!:".includes(before[before.length - 1]!) ? "The " : "the ";
      }
      const written = csm ?? `${kind} ${num}`;
      return `${article}${actas ? "ACTAS " : ""}${found.title} ${NOUN[found.kind]} (${written})`;
    },
  );
}
