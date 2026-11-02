import type { Exclusions } from "../quiz/bank";

export const MAX_EXCLUDED = 200;
const MAX_TOPIC_CHARS = 200;

export type Qualification = "ap" | "icp";

export interface UserSettings {
  qualification: Qualification | null;
  pacer: boolean;
  excludedSections: string[];
  excludedDocuments: string[];
  saved: boolean;
}

export const DEFAULT_SETTINGS: UserSettings = {
  qualification: null,
  pacer: false,
  excludedSections: [],
  excludedDocuments: [],
  saved: false,
};

export function parseTopicList(value: unknown): string[] | null {
  if (value === undefined || value === null) return [];
  if (!Array.isArray(value) || value.length > MAX_EXCLUDED) return null;
  if (value.some((v) => typeof v !== "string" || v.length === 0 || v.length > MAX_TOPIC_CHARS)) return null;
  return [...new Set(value as string[])];
}

export function parseExclusions(body: Record<string, unknown>): Exclusions | null {
  const sections = parseTopicList(body.excludedSections);
  const documents = parseTopicList(body.excludedDocuments);
  if (!sections || !documents) return null;
  return { sections, documents };
}

function jsonList(raw: string): string[] {
  try {
    const parsed = JSON.parse(raw) as unknown;
    return Array.isArray(parsed) ? parsed.filter((v): v is string => typeof v === "string") : [];
  } catch {
    return [];
  }
}

export async function readSettings(db: D1Database, userId: string): Promise<UserSettings> {
  const row = await db
    .prepare(`SELECT qualification, pacer, excluded_sections, excluded_documents FROM user_settings WHERE user_id = ?1`)
    .bind(userId)
    .first<{ qualification: Qualification | null; pacer: number; excluded_sections: string; excluded_documents: string }>();
  if (!row) return DEFAULT_SETTINGS;
  return {
    qualification: row.qualification,
    pacer: row.pacer === 1,
    excludedSections: jsonList(row.excluded_sections),
    excludedDocuments: jsonList(row.excluded_documents),
    saved: true,
  };
}

export function parseSettings(body: Record<string, unknown>): Omit<UserSettings, "saved"> | null {
  const q = body.qualification;
  if (q !== null && q !== "ap" && q !== "icp") return null;
  if (typeof body.pacer !== "boolean") return null;
  const exclusions = parseExclusions(body);
  if (!exclusions) return null;
  return { qualification: q, pacer: body.pacer, excludedSections: exclusions.sections, excludedDocuments: exclusions.documents };
}

export async function writeSettings(db: D1Database, userId: string, s: Omit<UserSettings, "saved">, now: number): Promise<void> {
  await db
    .prepare(
      `INSERT INTO user_settings (user_id, qualification, pacer, excluded_sections, excluded_documents, updated_at)
       VALUES (?1, ?2, ?3, ?4, ?5, ?6)
       ON CONFLICT (user_id) DO UPDATE SET qualification = excluded.qualification, pacer = excluded.pacer,
         excluded_sections = excluded.excluded_sections, excluded_documents = excluded.excluded_documents,
         updated_at = excluded.updated_at`,
    )
    .bind(userId, s.qualification, s.pacer ? 1 : 0, JSON.stringify(s.excludedSections), JSON.stringify(s.excludedDocuments), now)
    .run();
}
