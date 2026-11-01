import { Hono } from "hono";
import type { Context } from "hono";
import { apiError } from "../lib/http";
import type { AppEnv } from "../types";
import { corpusStatus, currentCorpusVersion, getDocument, listDocuments, parseView, type DocumentKind } from "./repo";
import { searchCorpus, syncVectors } from "./vectors";

const PUBLIC_CACHE = "public, max-age=300";
const GUIDELINE_KINDS: Record<string, DocumentKind[]> = { "": ["cmg", "csm"], cmg: ["cmg"], csm: ["csm"] };

async function listHandler(c: Context<AppEnv>, kinds: DocumentKind[]) {
  const [version, items] = await Promise.all([currentCorpusVersion(c.env.DB), listDocuments(c.env.DB, kinds)]);
  c.header("Cache-Control", PUBLIC_CACHE);
  return c.json({ corpusVersion: version, items });
}

async function detailHandler(c: Context<AppEnv>, kinds: DocumentKind[]) {
  const view = parseView(c.req.query("view"));
  if (!view) return apiError(c, 400, "bad_request", "Unknown view. Use ap, ap_pacer, icp or icp_pacer.");
  const doc = await getDocument(c.env.DB, c.req.param("id") ?? "", kinds, view);
  if (!doc) return apiError(c, 404, "not_found", "No such guideline.");
  c.header("Cache-Control", PUBLIC_CACHE);
  return c.json(doc);
}

export const guidelineRoutes = new Hono<AppEnv>();

guidelineRoutes.get("/", (c) => {
  const kinds = GUIDELINE_KINDS[c.req.query("kind") ?? ""];
  if (!kinds) return apiError(c, 400, "bad_request", "Unknown kind. Use cmg or csm.");
  return listHandler(c, kinds);
});
guidelineRoutes.get("/:id", (c) => detailHandler(c, ["cmg", "csm"]));

export const medicationRoutes = new Hono<AppEnv>();

medicationRoutes.get("/", (c) => listHandler(c, ["med"]));
medicationRoutes.get("/:id", (c) => detailHandler(c, ["med"]));

export const adminCorpusRoutes = new Hono<AppEnv>();

adminCorpusRoutes.use("*", async (c, next) => {
  const user = c.get("user");
  if (!user) return apiError(c, 401, "unauthorised", "Sign in first.");
  if (!user.isAdmin) return apiError(c, 403, "forbidden", "Admins only.");
  await next();
});

adminCorpusRoutes.get("/", async (c) => {
  const status = await corpusStatus(c.env.DB);
  return c.json({ ...status, vectorsAvailable: Boolean(c.env.AI && c.env.VECTORIZE) });
});

adminCorpusRoutes.post("/sync", async (c) => {
  const result = await syncVectors(c.env, Date.now());
  c.get("log").info("corpus_sync", { ...result });
  return c.json(result);
});

adminCorpusRoutes.get("/search", async (c) => {
  const q = (c.req.query("q") ?? "").trim();
  if (!q || q.length > 300) return apiError(c, 400, "bad_request", "Give a search of 1 to 300 characters.");
  const view = parseView(c.req.query("view"));
  if (!view) return apiError(c, 400, "bad_request", "Unknown view.");
  const hits = await searchCorpus(c.env, q, view);
  if (hits === null) return apiError(c, 503, "unavailable", "Vector search isn't configured in this environment.");
  return c.json({ hits });
});
