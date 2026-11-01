# Web Port Plan: Clinical Recall Assistant → multi-user web app

**Status:** Draft v2, 2026-10-31. Nothing built. Phase 1 (full review) must finish before any build work starts.

**Decisions locked (Oscar, 2026-10-31):**
1. **Cloudflare-native rewrite** (Option B below). The Python code is reference and offline-pipeline only.
2. **Three access tiers:** anonymous public users get **pre-generated questions only** (zero LLM spend); signed-in free users additionally get a **small monthly quota of fresh generation and of AI marking**; the site is public, sign-up required for the free tier.
3. **Quota numbers:** keep the recommendation (about 20 generations + 30 AI marks per month), to be re-set from the Phase 1 cost model.
4. **ACTAS only at launch.** Ambulance Tasmania data stays out of the public corpus; the multi-service schema (`service` column) is kept so AT can be added later.
5. **User uploads are deferred** to a later release.
6. **Web corpus = ACTAS guideline content only.** None of Oscar's personal material goes into the web version, now or later: no Notability notes, uni coursework, CPD docs, or REF docs. The build script enforces an allowlist (`source_type = "guideline"`) so nothing else can reach D1, Vectorize or the question bank.
7. **Later addition (post-launch): pathophysiology questions from a free, openly licensed source.** Candidates and licence checks are in Phase 7. These are labelled as non-ACTAS in the UI and kept in a separate corpus tier below the guidelines.
**Goal:** Move from a single-user Electron + local FastAPI app (bring-your-own API key) to a hosted web app where
(a) each user gets a free quota of generated questions, and (b) every generated question is saved to a database and
reused, so tokens are only spent on questions that don't already exist.

---

## 1. Current state (reviewed 2026-10-31)

**Shape.** Electron shell → spawns FastAPI on `:7777` → React 19 / Vite / Tailwind renderer. ~12.8k lines Python,
~7.8k lines TSX/TS, 156 frontend + 784 Python tests. Corpus: ACTAS CMGs (60 structured files) and Ambulance Tasmania
CPGs (multi-service registry in `services/registry.py`), plus optional personal Notability/CPD notes and user uploads.
Retrieval is ChromaDB (90 MB sqlite, per-service collections). Mastery/history is SQLite (`data/mastery.db`).

**Quiz flow today** (`quiz/agent.py`): pick mode → retrieve 5–15 chunks → one LLM call generates a question →
user answers → second LLM call evaluates against the same chunks → score recorded in `Tracker`.
Every question is generated fresh. Nothing is reused.

### What ports well
- Source corpus is **small** (~3 MB structured CMG JSON). Hosted vector search is cheap; no heavy infra needed.
- Question model already stores its source chunks (`source_chunks_json`), `source_citation`, `category`, `difficulty`,
  `question_type`, and a `service` column. That is most of a cacheable-question schema already.
- Provider abstraction (`llm/`) is clean; prompts are isolated and short.
- Multi-service registry (ACTAS/AT) and AP/ICP qualification filtering are real domain logic worth keeping.
- Data pipeline has a version tracker (`pipeline/*/version_tracker.py`), which is the hook for cache invalidation.
- Renderer is cleanly layered (`apiClient`, providers, hooks), so most UI survives with an auth + quota layer added.

### What blocks a web port (must change)
| # | Finding | Where | Why it matters on the web |
|---|---|---|---|
| 1 | **Single-user everywhere.** No `user_id` on mastery, history, blacklist, chunk coverage, settings. | `quiz/tracker.py`, `quiz/store.py` | Every table needs per-user scoping. |
| 2 | **Questions are deleted on every startup** (`_clear_stale`). Storage is ephemeral session scratch. | `quiz/store.py:45` | Opposite of the new requirement. Replace, don't extend. |
| 3 | **Active service is a global read from `settings.json`.** | `services/active.py` | Must be a per-request/per-user value. |
| 4 | **User-supplied API keys in `config/settings.json`;** `/settings` GET/PUT handles them. Three keys are currently populated locally. | `settings/router.py`, `config/` | Server-held keys only. Rotate the three local keys before any hosting work. |
| 5 | **Admin operations exposed as ordinary endpoints:** pipeline rerun, vector-store clear, CMG rebuild/refresh. | `settings/router.py:207-328` | Remove from the public API; move to an admin-only job runner. |
| 6 | **No auth, CORS is localhost/`file://`.** | `main.py` | Needs real auth, CSRF/CORS policy, rate limiting. |
| 7 | **Retrieval is a local persistent Chroma + in-process seeding thread.** | `quiz/retriever.py`, `seed.py` | Replace with a hosted vector store populated by an offline build step. |
| 8 | **User uploads** write to local disk and are mixed into the same index at 0.30 weight. | `upload/` | Per-user private storage, file validation, size limits, malware/abuse risk, and copyright exposure. |
| 9 | **Evaluation is a second LLM call per answer and is uncacheable** (every answer is unique). | `quiz/agent.py:evaluate_answer` | The free quota must cover this too, or the cost hole just moves. See §4. |
| 10 | **Electron/packaging code and artefacts**: `release/` 1.4 GB, `build/` 480 MB, `scripts/package-backend.*`, LM Studio provider, `BackendBootGate`, preload IPC. | repo-wide | Dead weight on the web; delete in the port. |

### Quality / hygiene debt to resolve in review (not blockers, but don't carry into a rebuild)
- Tests: 9 frontend + 11 Python failures, documented as stale (`KNOWN_TEST_FAILURES.md`). Fix or delete before porting so the suite is a trustworthy safety net.
- Disconnected features from the 2026-04-05 audit still open: dead "New Documentation" button, Guidelines scope picker ignored by Quiz, dose tables / flowcharts returned by API but never rendered, `Request Peer Review` is just a route change, flowchart pipeline is mock (`svg_mock`).
- Model IDs in `llm/models.py` are stale (Claude 4.x / GPT-5.4 / Gemini 3.x preview). Re-pick for current models and re-benchmark cost vs. quality.
- Four+ LLM providers + LM Studio: a hosted product needs one primary provider and at most one fallback.
- Repo state: on `feature/lmstudio-local-models` with a large uncommitted doc diff; a sibling `studyBotcode-archive/` duplicate (own `node_modules`), orphan `test_*.py`/`capture_assets.py` at the root, `tmp/`, `.DS_Store`s.
- Pinned docs (`CLAUDE.md`, `TODO.md`) describe the desktop architecture and will mislead agents working on the web version.

### Risks that are not engineering
- **Content rights.** *Resolved by Oscar 2026-10-31:* the ACTAS guidelines are publicly available, so public use is accepted. Still keep source attribution. Personal Notability notes and uni coursework (`CAA306` etc.) must **not** be published (deferred anyway).
- **Clinical safety / liability.** A cached wrong question is served to many users. Needs a report-an-error loop, a "study aid, not clinical guidance" disclaimer, and a way to pull a question instantly. (`InfoERRORS.md` is the desktop version of this.)
- **Privacy.** Accounts + study history = personal information (Australian Privacy Act). Keep data minimal, pick an AU/near region if practical, publish a short privacy policy.
- **Cost abuse.** A free LLM quota invites multi-accounting. Google sign-in requires a verified Google account (checked via `email_verified`); add Turnstile later if abuse appears.

---

## 2. Target architecture

### Decision: Cloudflare-native TypeScript rewrite (chosen)

Proposed stack, to be validated against current Cloudflare docs in Phase 1 (use the `cloudflare`, `workers-best-practices`
and `wrangler` skills; do not rely on memory for limits or pricing):

| Concern | Proposal |
|---|---|
| API | Workers (TypeScript, Hono or similar), one Worker for the API, cron/Queue consumers for background jobs |
| Front end | Existing React/Vite SPA, served from Workers static assets (or Pages); Tailwind design system carried over |
| Relational data | D1 (users, question bank, attempts, mastery, ledger, reports). Fall back to Postgres via Hyperdrive only if D1 limits bite in the review |
| Vector search | Vectorize for guideline chunks and question near-dup checks; embeddings via Workers AI. **Stays on the Workers Free plan** (2026-11-01): ~500 chunks × 768 dims ≈ 0.4M of the free 5M stored dimensions; 30M free queried dimensions ≈ 39k searches a month. Keep it optional: generation can pick chunks by guideline ID and near-dup checks can run offline in the bank build |
| LLM calls | **Gemini or GLM (Z.ai)**, chosen by Phase 1 benchmark; routed through AI Gateway if it supports the chosen provider (verify), for spend logs, rate limits and response caching. Keep the provider behind one small interface so switching is a config change |
| Per-user quota counters | Durable Object (or D1 with atomic update) so concurrent requests cannot overshoot quota |
| Auth | **Google sign-in only** (OpenID Connect with PKCE; Oscar, 2026-11-01). No email sending, so no Workers Paid or sending domain needed |
| Rate limiting / abuse | Workers rate limiting binding + per-IP caps for anonymous traffic |
| Bulk pre-generation | Offline job (Queue/Workflow or local script) using the provider batch API, writes to the question bank |
| Corpus build | **Stays Python, offline**: existing scrape/extract/chunk pipeline outputs structured JSON, a build script loads D1 + Vectorize. No Python runs in production |

Consequence: the quiz, retrieval, tracker and store logic is re-implemented in TypeScript, so the Python tests are
ported as specs, not run. The Phase 1 test triage therefore matters more (which of the 784 tests encode real behaviour
worth porting).

### Data model (core of the token-saving goal)
```
users(id, email, created_at, plan, free_gen_used, free_eval_used, quota_period_start)
question_bank(
  id, service, guideline_id, source_chunk_ids[], source_snapshot_json,   -- snapshot = chunk text at generation time
  question_text, question_type, difficulty, category, qualification_scope, -- AP | ICP
  source_citation, primary_chunk_index,
  source_type, licence, attribution,   -- "guideline" only at launch; later "pathophys"
  content_hash,            -- normalised question text, exact-dup guard
  embedding,               -- near-dup guard (cosine threshold)
  prompt_version, model_id, corpus_version,
  status,                  -- active | flagged | retired
  times_served, times_reported, created_at)
user_question_seen(user_id, question_id, first_seen_at)     -- never re-serve unless bank exhausted
attempts(id, user_id, question_id, score, elapsed, user_answer, evaluation_json, created_at)
mastery / blacklist / chunk_coverage  (existing tables + user_id)
usage_ledger(id, user_id, kind[gen|eval], model_id, tokens_in, tokens_out, cost_est, cache_hit, created_at)
corpus_chunks(id, service, source_file, content, category, qualification, version, embedding)
reports(id, user_id, question_id, reason, created_at)
```

### Serve-from-bank flow (replaces `generate_question`)
1. Resolve filters (service, qualification scope, mode/topic/guideline, difficulty) → candidate set of `active` bank questions.
2. Exclude `user_question_seen`. If any remain → pick one (weighted to weak categories for `gap_driven`) → **zero LLM cost, zero quota**.
3. Only if none remain → check quota → run the existing retrieve-and-generate path → dedup (hash, then embedding similarity) → insert to bank → serve → decrement quota.
4. If generation produced a near-duplicate of an existing bank question, serve the existing one and refund quota.

### Cost levers beyond the cache
- **Pre-seed the bank offline.** The corpus is finite (~60 guidelines × 2 services × a handful of angles). Generate a few thousand questions in bulk with the provider's batch API (about half price) during Phase 4, with a clinical spot-check. Most users then never trigger live generation.
- **Prompt caching** on the generation/evaluation system prompts.
- **Cheapest adequate model** for generation; keep a stronger one only if eval quality demands it (benchmark in Phase 1/4).
- **Self-grade/Reveal path stays free** (already exists in the UI): evaluation LLM call is opt-in via quota.

### Access tiers
| Tier | Questions | AI marking | LLM spend |
|---|---|---|---|
| **Anonymous (public)** | Pre-generated bank only, rate-limited per IP | None. Self-grade via "Reveal Reference" only | Zero |
| **Signed-in free** | Bank first (unmetered), plus a **small monthly quota of fresh generation** (starting 20) when the bank has nothing unseen for their filter | **Small monthly quota of AI marking** (starting 30) | Capped per user |
| Later (not now) | Paid tier or BYO key to lift caps | | |

- Anonymous progress is kept in the browser only (local storage); on sign-up it is offered for import into the account.
- Hard per-user and global daily caps as a circuit breaker, plus a global spend alarm; kill switch to turn off live generation and marking (everyone falls back to bank + self-grade).
- Quota resets monthly; show remaining quota in the UI and say plainly when a question came from the library vs was generated.
- Starting numbers are placeholders. The Phase 1 cost model sets the final ones from real token counts and the expected cache-hit ratio.

---

## 3. Phases

Each phase ends with a written handoff in `docs/NEXT_SESSION.md`. Use Opus for Phase 1 and for security review; Sonnet otherwise.

### Phase 0: Freeze and clean (small)
- Commit or discard the pending doc diff; decide the fate of `feature/lmstudio-local-models`; tag the last desktop version (`desktop-final`).
- Rotate the three API keys in `config/settings.json`; confirm `.env`/`settings.json` are not in git history.
- Delete `studyBotcode-archive/` duplicate and orphan root scripts only **after** asking Oscar (archive rule in root CLAUDE.md).
- Create a new repo/folder for the web build so the desktop app remains maintainable; keep this plan with it.
- **Rescrape the ACTAS CMGs before the rewrite.** The scraped data is out of date (for example CSM.C07 is missing). Re-run the ACTAS pipeline, then re-run `scripts/backfill_actas_qualifications.py` and `scripts/report_actas_scope.py`, and have Oscar check the new scope report (`docs/review/actas-scope-tagging.md`) before Phase 3 builds the corpus from it.
  - *2026-11-01:* skills and monographs moved into `data/services/actas/structured/{csm,med}/` and the legacy `data/cmgs/structured/` removed (review C-3). The pipeline has a new `dates` stage that copies version dates from the CMG list page (review C-4). The scrape itself is still to do: cloud threads cannot reach `cmg.ambulance.act.gov.au` until the environment's network allowlist includes it. Run order: `python -m pipeline.actas.orchestrator`, then the backfill script, then the report script.

### Phase 1: Thorough review (REQUIRED before any build)
Output: `docs/review/web-port-review.md` with severity-ranked findings and a go/no-go per area. Slices, each reviewable in isolation:
1. **Backend correctness & coupling:** quiz agent, retriever, tracker, store, settings, services; list every global/singleton/local-path assumption; decide Option A vs B from evidence.
2. **Frontend:** page-by-page keep/cut/change; dead UI; Electron-only code; accessibility; mobile layout (a web app will be used on phones, the desktop design was not).
3. **Data & pipeline:** corpus completeness and freshness per service, dose-table accuracy (`test_cmg_dose_accuracy`), flowchart gap, chunking quality, ICP/AP tagging correctness, `InfoERRORS.md` items resolved.
4. **Prompts & AI quality:** grading calibration, question quality sample (~50 per service, human-rated), duplicate rate, model/cost benchmark on current models, JSON-parse failure rate.
5. **Security & abuse:** threat model for auth, uploads, prompt injection via uploaded docs, quota bypass, secrets, rate limits. (Opus.)
6. **Tests:** triage the 20 failing tests (fix/delete), measure real coverage of quiz/retrieval paths that the port will touch, add characterisation tests where thin.
7. **Disclaimer and privacy:** disclaimer wording, source attribution, privacy policy basics including which LLM provider receives user answers. (Content publication is already decided: public ACTAS guidelines are fine to use.)
8. **Cost model:** estimate tokens per generation/evaluation from real logs, project monthly spend at 100 / 1,000 / 10,000 users with expected cache-hit ratio, set the free quota from the numbers rather than guessing.

Gate: Oscar reviews the findings and signs off on scope, hosting option, quota numbers and the content-rights position. Nothing in Phases 2+ starts before this. **Signed off 2026-11-01.**

### Phase 2: Foundations
New repo with Workers project (`wrangler` config, dev/staging/prod environments), CI/CD, D1 migrations, secrets via Workers secrets, auth (email magic link only) with Turnstile, rate limiting, AI Gateway set up with a spend cap, React shell on static assets, structured logging and error tracking. Deliverable: a deployed "hello world" with working sign-in and an anonymous/signed-in distinction in the API.
- *2026-11-01 (later the same day):* sign-in switched to **Google only** at Oscar's request; email links, Email Service and Turnstile removed. Nothing in Phase 2 now needs Workers Paid.
- *2026-11-01:* built in `web/` in this repo rather than a new repo (cloud threads can't create repositories; it can be split out later with `git subtree split`). Done: Workers + Hono API and React shell on one Worker, dev/staging/production config, D1 migration for users/link tokens/sessions, magic-link sign-in with Turnstile, rate-limit bindings, CSRF/origin guard, structured JSON logs with Workers Logs, Gemini-through-AI-Gateway client that returns token usage (H-8 for the web code), Web CI (typecheck, Worker + client tests, axe checks, build) and a deploy workflow. **Not yet deployed:** needs the one-time setup in `web/README.md` (Google OAuth client, D1 in `oc`, AI Gateway spend limit, secrets).

### Phase 3: Data layer and corpus (ACTAS only)
Offline Python build step turns `data/services/actas/structured/` (guidelines, `csm/`, `med/`) into `corpus_chunks` rows in D1 plus embeddings in Vectorize, with `corpus_version`. Guidelines and medication read APIs served from D1/static JSON (the current pre-built `guidelines-index.json` / `medications-index.json` approach suits this). Admin-only refresh job replaces `/settings/cmg-refresh`, `/cmg-rebuild`, `/pipeline/rerun`. **Excluded from the web version:** all of Oscar's personal material (Notability notes, uni coursework, CPD docs, REF docs), enforced by a `source_type = "guideline"` allowlist in the build script plus a test that fails the build if any other type appears. **Deferred:** Ambulance Tasmania data and user uploads. Each corpus chunk and each question carries `source_type`, `licence` and `attribution` fields now, so a second source can be added later without a schema change.

- *2026-11-01:* built. `src/python/web_corpus/build.py` turns the 194 ACTAS documents (56 CMGs, 103 skills, 35 MEDs) into D1 rows (`corpus_documents`, per-scope `corpus_document_bodies`, ~760 `corpus_chunks`) with a deterministic `corpus_version` and per-document `checksum` (review C-4). Allowlist enforced three times: the build rejects non-guideline inputs, the tests cover it, and D1 `CHECK (source_type = 'guideline')`. Embeddings via Workers AI into Vectorize (free plan), synced by the daily cron or an admin button. Guideline, clinical skill and medication pages with an AP / ICP / PACER scope filter. The scraped data is committed, so the build runs anywhere; only the production load needs Oscar's `wrangler` (steps in `web/README.md`).

### Phase 4: Question bank and quota (the core feature)
Schema above; serve-from-bank flow; dedup (hash + embedding); `usage_ledger`; tier enforcement (anonymous = bank only, signed-in = bank then quota); atomic quota counters; clear UI messaging ("served from library" vs "generated new", remaining quota); report-a-question flow with auto-flag threshold; **bulk pre-seeding with the batch API and a sampled clinical review, which must be done before launch because anonymous users depend on it entirely**; cache invalidation by `corpus_version`/guideline change (retire or regenerate affected questions). Bank coverage target: every ACTAS guideline and AP/ICP scope has enough questions across difficulties that an anonymous user does not run dry in a normal session (size from the Phase 1 analysis).
- *2026-11-01:* prompt fixes C-5, H-5 and H-11 done in the Python reference code. The behaviour to port (store the primary chunk, mark against it only, treat unreadable marks as refunded errors) is in `web/docs/prompts.md`.

### Phase 5: Port the product surface
Per-user mastery/history/blacklist; per-user service + qualification settings (replacing the global `active_service`); Dashboard, Quiz, Feedback, Guidelines, Medication, Library (trimmed), Settings (stripped of keys/admin). Responsive/mobile pass. Remove Electron IPC, boot gate, packaging.

### Phase 6: Hardening and launch
Security review (Opus), load and cost test with synthetic users, abuse tests on quota, backup/restore drill, privacy policy and disclaimers live, soft launch to a small group, monitor cache-hit ratio and spend, then widen.

### Phase 7: After launch (not committed)
Paid tier or BYO key, spaced repetition on the bank, shared decks, admin question-review UI.

**Pathophysiology questions from a free source.** Do a licence check before choosing; my understanding of the candidates (verify each against the source's current terms, I have not checked them in this session):
| Source | Licence (as I understand it) | Fit |
|---|---|---|
| **OpenStax** (Anatomy & Physiology 2e; nursing titles) | **CC BY-NC-SA 4.0, and generative AI use needs OpenStax's written permission** (verified 2026-10-31 on the A&P 2e pages; I first assumed CC BY, which was wrong) | Best content fit, but blocked until permission is granted. Non-commercial only |
| **Wikipedia** | CC BY-SA 4.0 | Usable with attribution, but share-alike applies to derived content; quality varies, so restrict to well-reviewed medical articles |
| **StatPearls** (NCBI Bookshelf) | CC BY-NC-ND 4.0 | **Likely a problem**: non-commercial and no-derivatives terms conflict with generating and republishing questions from it. Check with the publisher before use |
| **MedlinePlus** (US NLM) | Public domain for most content | Patient-level, probably too shallow |

**Source not yet chosen (Oscar, 2026-10-31: leave options open).** OpenStax was the first preference; the licence check done the same day shows it needs permission before use. The Anatomy & Physiology 2e pages state (read via fetch on the book's own pages, two separate pages agreeing):
- Licence is **CC BY-NC-SA 4.0**, not CC BY as I earlier assumed. Reuse and modification are for **noncommercial purposes only**, with attribution, and derivatives must carry the same licence.
- **Using the content to train LLMs or in generative AI products requires OpenStax's prior written permission.** Generating questions with an LLM from the text, then serving them, plausibly counts as a generative AI product.

So OpenStax stays a candidate, but it is **not usable until permission is obtained**. Decide the source after the Phase 1 review, when the launch is further along. If OpenStax is pursued, the steps are:
1. Email OpenStax (their licensing/permissions contact) describing the use: free public study site, LLM-generated questions from specific chapters, attribution shown, no revenue so far; ask for written permission. Oscar sends this; I can draft it.
2. Check the specific books wanted (A&P 2e, any nursing/pathology titles) individually; terms may differ per book.
3. If permission is refused or conditional on staying non-commercial, note that the planned paid tier would conflict, so the pathophys tier must stay free or be dropped from paid features.
4. Fallbacks if OpenStax declines (all unverified, licence-check each before use): Wikipedia medical articles (CC BY-SA, share-alike), open-access research and review papers licensed CC BY via PubMed Central (per-article licence), and US government public-domain health material.

Plan for it once a source is cleared: add it as a separate corpus tier (`source_type = "pathophys"`) below guidelines in the source hierarchy, store licence and attribution on every chunk and question, label these as "background science, not ACTAS guideline", and generate through the same bank-first flow. Re-run the Phase 1 quality sampling on a sample before bulk pre-seeding.

---

## 4. Success measures
- **Cache-hit rate** ≥ 80% of served questions after pre-seeding (target to validate in Phase 1 cost model).
- **LLM cost per active user per month** under a set ceiling (decided in Phase 1).
- **Question error rate:** reported/flagged < 2% of served; flagged questions retired within a day.
- No user can exceed free quota by more than the agreed margin in abuse tests.
- Desktop test suite green (or consciously trimmed) before porting; web suite green at each phase end.

## 5. Decisions

Resolved (see top of file): Cloudflare rewrite; public with anonymous = pre-generated only and signed-in free tier with small generation and marking quotas; ACTAS only; uploads and personal notes deferred; starting quota about 20 generations / 30 marks per month.

Also resolved (Oscar, 2026-10-31):
- **Content rights:** the ACTAS guidelines are publicly available, so public use of the content is accepted. Keep clear source attribution and the "study aid, not clinical guidance" disclaimer; no further permission work planned. (Phase 1 slice 7 shrinks to disclaimer wording and privacy basics.)
- **Model family:** Gemini or GLM (Z.ai) for generation and marking, not Claude.

Resolved at Phase 1 sign-off (Oscar, 2026-11-01; see `docs/review/web-port-review.md` §10):
- **Models:** Gemini 3.8 Flash for question generation and bank pre-seeding (batch API); Gemini 3.5 Flash-Lite for live marking. GLM isn't used: it credited wholly wrong answers in the benchmark (`docs/review/model-bench/README.md`). Because only Google receives user answers, the privacy policy names Google.
- **Database:** D1 (the review found the data volumes are tiny against D1's limits).
- **Quota:** keep the placeholders (20 generations and 30 marks per signed-in user per month). Oscar sets provider spend caps as the backstop, alongside the global circuit breaker.
- **Auth:** ~~email magic link only~~ **Google sign-in only** (Oscar, 2026-11-01, changed the same day). Accounts are keyed on Google's `sub`.
- **Cost:** stay on free tiers where possible (Oscar, 2026-11-01). Vectorize's free tier covers the ACTAS corpus.
