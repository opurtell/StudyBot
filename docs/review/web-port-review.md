# Web Port Review (Phase 1, initial pass)

**Date:** 2026-10-31
**Scope:** Phase 1 of `docs/web-port-plan.md`, all eight slices, reviewed against `main` at `99aa183` in a clean cloud clone.
**Status:** Initial pass. Slices 1, 2, 3, 5, 6 are complete from code and data. Slices 4 and 8 are complete as far as
static review and published prices allow; the live model benchmark and the human-rated question sample still need
API keys and Oscar's clinical judgement. Slice 7 gives draft positions only.

Severity: **Critical** = must be fixed or decided before Phase 2. **High** = must be handled in the phase that touches it.
**Medium** = carry as a ticket. **Low** = note only.

---

## 0. Headline

**Go for the Cloudflare rewrite, with four pre-conditions:**

1. **Fix the corpus build inputs** (C-3, C-4). The current per-service data path drops all 98 clinical skills and 35
   medication monographs from the quiz index, and there is no version date on any guideline. The web build script must
   not inherit this.
2. **Benchmark marking before choosing a model** (H-7). The benchmark harness the plan relies on
   (`scripts/bench-local-models.py`) is not on GitHub. It only exists on Oscar's local branch, if at all.
3. **Make the LLM interface return token usage** (H-8). `complete()` returns a bare string today, so there is nothing
   to feed `usage_ledger` or the cost model.
4. **Size the bank per filter cell, not in total** (cost model §8). Live generation only fires when a user exhausts
   their filter, and single-guideline filters will run dry quickly.

Phase 0 has not been done (it needs Oscar's machine): the three local API keys still need rotating and `desktop-final`
is not tagged. No keys or `settings.json`/`.env` files appear anywhere in this repo's git history (checked all 76 commits).

### Go / no-go per area

| Area | Verdict | Why |
|---|---|---|
| Rewrite in TypeScript on Workers (Option B) | **Go** | Backend logic is small (quiz package ~1,300 lines) and every module assumes one user and local files. Nothing worth wrapping. |
| D1 for relational data | **Go** | Data volumes are tiny against the 10 GB limit. See §8. |
| Vectorize + Workers AI embeddings | **Go** | Corpus is ~95k tokens. Stored dimensions stay inside the paid plan's included 10M. |
| Reusing the React renderer | **Go, with a mobile rebuild of the shell** | Pages are cleanly layered, but there is effectively no responsive layout (9 breakpoint classes in the whole renderer). |
| Corpus as-is | **No-go until C-3 / C-4 fixed** | Clinical skills and monographs missing from the service path; no version dates. |
| Prompts as-is | **No-go until C-5 and H-5 fixed** | Literal f-string leaking into the generation prompt; parse failures recorded as "incorrect". |
| Model choice | **Go** | Gemini 3.8 Flash for generation, 3.5 Flash-Lite for marking (benchmark, 2026-11-01). |
| Test suite as safety net | **Go after triage** | 92% line coverage on `quiz/` and `services/`, but heavy mocking let two real bugs through (C-2, C-5). |

---

## 1. Backend correctness and coupling

### Findings

| ID | Sev | Finding | Evidence |
|---|---|---|---|
| C-1 | Critical | **Single-user state in every table and singleton.** `quiz_history`, `blacklist`, `chunk_coverage`, `categories` have no user column. `Tracker`, `QuizStore`, `Retriever` and the settings cache are process-wide singletons. | `quiz/tracker.py:22-50`, `quiz/store.py:224-236`, `quiz/retriever.py:19`, `settings/router.py:45-58` |
| C-2 | Critical | **Guideline-scoped quizzes silently fall back to the whole section.** `SessionConfig.guideline_id` is set by `/session/start` but `quiz_sessions` has no `guideline_id` column, so it is dropped on save. Reproduced: round-trip returns `None`. This is the root cause of the 2026-04-05 audit item "Guidelines scope picker ignored by Quiz". | `quiz/store.py:23-45`, `quiz/router.py:107-125` |
| H-1 | High | **The `service` column in `QuizStore` is never used.** The router calls `store_question`, `get_question`, `store_session` without `service=`, so every row is written as `actas` regardless of the active service. The plan's §1 claim that the question model "already has a service column" is true of the schema only. | `quiz/router.py:121,144,172-173,185` |
| H-2 | High | **Active service is read from `settings.json` on every call**, including inside prompt building (`build_generation_prompt`) and section resolution. Must become a request parameter. | `services/active.py:30-38`, `quiz/agent.py:26,316` |
| H-3 | High | **Re-marking is unbounded.** `/question/evaluate` has no check that a question was already marked, so the same answer can be re-submitted for repeated LLM calls and repeated history rows. On the web this is a quota-drain and a mastery-inflation path. | `quiz/router.py:183-215` |
| H-4 | High | **Mastery categories are free text chosen by the LLM** (`parsed.get("category")`), so the heatmap can fragment ("Cardiac" vs "Cardiology"). On the web, take category from the guideline's `section`, not from the model. | `quiz/agent.py:198-203`, `quiz/tracker.py:123` |
| M-1 | Medium | **Mixed distance scales.** `personal_*` collections use cosine, `guidelines_*` use Chroma's default (L2), and both are ranked together by `-distance`. Moot on the web (guidelines only) but don't port the ranking formula as-is. | `quiz/retriever.py:48-51,94-106` |
| M-2 | Medium | `get_random_chunk` loads every ID in a collection per call. Fine locally; the D1 equivalent should sample with `ORDER BY random() LIMIT 1` or a precomputed index. | `quiz/retriever.py:166-196` |
| M-3 | Medium | `previous_questions` grows unbounded inside one session and is appended to every generation prompt. Cap it (last 10) or replace with the bank's dedup. | `quiz/router.py:149-153` |
| L-1 | Low | Random mode offers topics with no guideline section ("Pathophysiology", "ECGs", "Mental Health"). With a guideline-only web corpus these just become unfiltered semantic queries. Fine, but relabel or drop them. | `quiz/agent.py:263-278` |

### Logic worth porting as specs

- `services/qualifications.py` (closure of base + endorsements) and the AP/ICP visibility filter in `retriever._build_where`.
- `Tracker.get_mastery`, `get_streak`, `get_weak_categories` (39 tests encode the behaviour).
- ICP content splitting in `pipeline/actas/chunker.py` (stays Python, offline).
- Everything else in `quiz/` should be re-specified, not ported: the bank-first flow replaces `generate_question` and `QuizStore`.

### Option A vs B

The evidence supports the locked decision (B). Every backend module is coupled to local files (`paths.py`), a local
Chroma, a global settings file, or a process singleton. Wrapping it would mean rewriting the same parts anyway.

---

## 2. Frontend

| Page / component | Verdict | Notes |
|---|---|---|
| `Dashboard` | Keep, change | Needs per-user data and an anonymous variant (local-storage progress). |
| `Quiz`, `useQuizSession`, `useQuizShortcuts` | Keep, change | Add "from library / newly generated" label, quota remaining, report button. Keyboard shortcuts are good; add touch equivalents. |
| `Feedback`, `FeedbackSplitView` | Keep, change | Relies on router `location.state`; a page refresh loses it. On the web, load by attempt ID so the URL is shareable and refresh-safe. |
| `Guidelines` | Keep, fix | Flowcharts render as `JSON.stringify` output (`pages/Guidelines.tsx:378-381`). Every structured file has `flowchart: null`, so hide the section until the flowchart pipeline exists. |
| `Medication` | Keep | Read-only, maps well to static JSON. |
| `Library`, `UploadDialog`, `CleaningFeed`, `sources/` | **Cut for launch** | Uploads and personal sources are out of scope. The "New Documentation" button now works (audit item is stale). |
| `Settings` | Cut down | Remove API keys, model pickers, pipeline rerun, vector store, CMG refresh. Keep theme, qualification (AP/ICP), blacklist, account. |
| `ServiceSetupModal`, `ServiceProvider` | Simplify | ACTAS only at launch: keep the provider shape, replace the modal with a qualification picker. |
| `BackendBootGate`, `useBackendStatus`, `DevelopmentDiagnostics`, `src/electron/` | **Cut** | Electron-only. |
| `lib/apiClient.ts` | Keep, change | `API_BASE` is hard-coded to `http://127.0.0.1:7777`; make it relative. Add auth/CSRF handling. |
| `App.tsx` routing | Change | `HashRouter` → `BrowserRouter` for real URLs. |

**Mobile (High, H-6).** The sidebar is a fixed `w-64` panel and the whole renderer has 9 responsive breakpoint classes.
Plan a responsive shell (bottom nav or drawer under `md`) before porting pages, not after.

**Accessibility (Medium).** 46 `aria-`/`role` attributes across the renderer. No audit has been run. Add an axe check to
the web CI in Phase 2 rather than auditing the desktop UI now.

**Frontend tests.** 9 of 156 fail (see §6). 4 `tsc --noEmit` errors (unused imports in `ServiceProvider.tsx` and two test files).

---

## 3. Data and pipeline

| ID | Sev | Finding | Evidence |
|---|---|---|---|
| C-3 | Critical | **Clinical skills and medication monographs are missing from the per-service corpus.** `data/services/actas/structured/` holds 56 CMGs and 2 index files only. The 98 CSMs and 35 MED monographs live only in the deprecated `data/cmgs/structured/{csm,med}/`. `seed.py` passes the services path to the chunker, which looks for `csm/` and `med/` subfolders there and finds none. A fresh install therefore quizzes on CMGs only. | `paths.py:37-52`, `seed.py:278-285`, `pipeline/actas/chunker.py:97-111` |
| C-4 | Critical | **No guideline has a version date.** `version_date` is `null` in all 56 CMGs and all 35 MED files. The plan's cache invalidation (`corpus_version`, retire questions when a guideline changes) needs a per-guideline change signal. Use the existing `checksum` field per guideline instead of dates, and record it on every bank question. | `data/services/actas/structured/*.json` |
| H-9 | High | **AP/ICP tags on dose entries are whole-medication, not per-indication.** Every dose entry for a given drug carries the same tag (e.g. all 594 adrenaline entries are `AP`, all 105 midazolam `AP`, all 120 sodium bicarbonate `ICP`). If any of those drugs has indications with different scope, one group of users gets wrong-scope questions. **Needs Oscar's clinical check.** Full list in Appendix A; RSI doses contradict CMG 3A's own ICP-only flag. | `data/services/actas/medications/*.json` |
| H-10 | High | **`source_type` mismatch with the plan.** The chunker writes `source_type: "cmg"`; the plan's allowlist is `source_type = "guideline"`. Pick one value and make the build-script test assert it, or the allowlist will reject the whole corpus (or, worse, be loosened to make it pass). | `pipeline/actas/chunker.py:154+` |
| M-4 | Medium | **Thin dose data for some medicines.** Fentanyl 1 entry, calcium chloride 1, ipratropium 1, salbutamol 2, oxygen 1,344. Five formulary medicines (aspirin, droperidol, glucagon, olanzapine, LMX4) have no file in `services/actas/medications/`. Some of this may be correct (fixed doses); worth a check against the live CMG site before bulk generation. | same |
| M-5 | Medium | **Flowcharts: none extracted.** `flowchart` is `null` everywhere. Questions that depend on algorithm structure will be weak. Not a launch blocker. | |
| M-6 | Medium | `test_cmg_dose_accuracy` fails because it reads `dose_lookup` from MED monographs, which is `null` in all 35. Dose data actually lives on the CMG files and in `services/actas/medications/`. The test is stale, not the data, but it means **there is currently no passing dose-accuracy test**. Rewrite it against the medications index. | `tests/python/test_cmg_dose_accuracy.py` |
| L-2 | Low | `InfoERRORS.md` has no entries, so nothing to resolve. | |

**Corpus size** (for §8): CMGs ~156k characters, CSMs + MEDs ~223k characters, so ~380k characters or roughly 95k tokens.
Chunks are capped at 300–1,000 tokens by type (`MAX_TOKENS`, `chunker.py:29`).

---

## 4. Prompts and AI quality

Static review only. The ~50-question human-rated sample and the model benchmark need API keys and clinical judgement.

| ID | Sev | Finding | Evidence |
|---|---|---|---|
| C-5 | Critical | **Fixed 2026-11-01** (desktop; port spec in `web/docs/prompts.md`). **Broken generation prompt.** The JSON example in the generation system prompt is a plain string, not an f-string, so the model literally sees `"source_citation": f"e.g. {svc.short_name} CMG 14.1"`. Verified by rendering the prompt. Citations that come back may be malformed or copy the placeholder. | `quiz/agent.py:44-55` |
| H-5 | High | **Fixed 2026-11-01** (desktop; port spec in `web/docs/prompts.md`). **Parse failures are scored as "incorrect".** If the marking response is not valid JSON, `evaluate_answer` returns `score="incorrect"` and it is recorded in mastery. On the web this also burns a marking credit. A parse failure should be an error, refunded, and never recorded. | `quiz/agent.py:225-237` |
| H-11 | High | **Fixed 2026-11-01** (desktop; port spec in `web/docs/prompts.md`). **Marking is graded against all five retrieved chunks**, not the one the question came from. This inflates input tokens about 5× and lets the grader credit facts from unrelated chunks. Grade against the primary chunk (plus its neighbours if needed); the bank should store that chunk. | `quiz/agent.py:212`, `primary_chunk_index` |
| M-7 | Medium | No provider uses a structured-output / JSON mode, and nothing records model, prompt version or token counts. Use JSON schema output on whichever provider is chosen. | `llm/google_provider.py`, `llm/zai_provider.py` |
| M-8 | Medium | AP-scope enforcement for generation relies partly on a prompt instruction. Retrieval filtering is the real guard; keep it, and add an AP/ICP check to the bank QA sample. | `quiz/agent.py:38-40` |
| M-9 | Medium | Model IDs in `llm/models.py` are out of date. Current options (checked 2026-10-31): Gemini 3.8 Flash and 3.5 Flash-Lite; GLM-5.3, 5.3-Flash, 5.3-FlashX. | `llm/models.py:13-36` |

### Still to do for this slice
1. Recover or rewrite the benchmark harness (H-7, below), then run it on Gemini 3.8 Flash, 3.5 Flash-Lite, GLM-5.3-Flash
   and GLM-5.3-FlashX for marking. Measure: strict JSON rate, grading agreement with the labelled set, fabricated credit,
   verbatim-quote grounding, latency, cost per call.
2. Generate ~50 ACTAS questions per candidate model; Oscar rates them for accuracy, scope and usefulness.
3. Measure the duplicate rate in that sample (hash + embedding).

| ID | Sev | Finding |
|---|---|---|
| H-7 | High | `scripts/bench-local-models.py` and its labelled grading set are referenced by the plan and `NEXT_SESSION.md` but **are not on `main` or any remote branch**. The `feature/lmstudio-local-models` branch is not pushed either. Push it from Oscar's machine, or the benchmark has to be rebuilt. |

---

## 5. Security and abuse

The desktop app has no auth by design. These are findings against the planned web design plus code that would be
dangerous if carried over.

| ID | Sev | Finding / requirement |
|---|---|---|
| C-6 | Critical | **`GET /settings` returns API keys in clear text** and `PUT /settings` writes arbitrary config. Admin endpoints (`/settings/pipeline/rerun`, `/cmg-rebuild`, `/cmg-refresh/run`, `/vector-store/clear`) are unauthenticated. None of this may exist in the web API. Keys go in Workers secrets; admin jobs go behind a separate admin auth or stay offline. (`settings/router.py:90-328`) |
| H-12 | High | **Quota bypass routes to close:** repeated marking of the same question (H-3); parallel requests racing the counter (plan already proposes a Durable Object or atomic D1 update; use `UPDATE … SET used = used + 1 WHERE used < limit` and check `changes`); multi-accounting (email verification + Turnstile, as planned); a refund path that can be triggered on purpose (only refund on server-detected near-duplicates or parse failures, never on client say-so). |
| H-13 | High | **Prompt injection through the user's answer** is direct: the answer is concatenated into the marking prompt. Impact is mostly self-inflicted (a user can talk the grader into "correct"), but it also lets anyone make the model emit arbitrary text that is shown back to them. Mitigate with structured output, a delimiter-wrapped answer field, an answer length cap (e.g. 2,000 characters), and never letting marking output reach other users. |
| H-14 | High | **Shared LLM output.** Bank questions are generated once and shown to everyone. `react-markdown` is used without raw HTML (safe from script injection), but links in generated text would render. Strip links and images from question and feedback text, and keep the report/retire loop from the plan. |
| M-10 | Medium | Upload handler reads the whole file into memory before the size check (`upload/router.py:~145`). Irrelevant at launch (uploads deferred) but don't port it. |
| M-11 | Medium | CORS today allows `file://` and `null` origins when packaged. The web API should be same-origin only (SPA and API on one Worker), which avoids CORS entirely. |
| L-3 | Low | No secrets found in git history. Keep `config/settings.json` out of the web repo entirely. |

Phase 6's Opus security review should re-check the actual Workers code; this list is the input to it.

---

## 6. Tests

Run on 2026-10-31 in a clean clone:

| Suite | Result |
|---|---|
| Python (`pytest tests/`) | **755 passed, 11 failed, 18 skipped** |
| Frontend (`vitest run`) | **147 passed, 9 failed** (156 tests, 33 files) |
| Typecheck (`tsc --noEmit`) | **4 errors** (unused imports) |

`KNOWN_TEST_FAILURES.md` is stale: it lists 17 frontend + 4 Python failures from April. None of the four Python failures
it lists still fail, and none of the 11 current ones are on it. Update it, or replace it with this table.

### Triage of current failures

| Test | Cause | Action |
|---|---|---|
| `test_cmg_dose_accuracy` × 2 | Reads `dose_lookup` from MED files (all `null`); data lives elsewhere | **Fix** (rewrite against medications index). This is the only dose-accuracy safety test. |
| `pipeline/at/test_chunker.py` × 4 | `guidelines_at` collection not created by the AT chunker in the test setup | **Leave** (AT out of scope for web); fix in a desktop test-repair PR |
| `llm/test_google_provider.py` × 3 | Tests expect the legacy `google.generativeai` call shape; provider now uses `google.genai` | **Delete** with the provider rewrite |
| `llm/test_factory.py::test_create_client_unknown_provider_raises` | Uses `openai` as the "unknown" provider, but OpenAI is now supported | Delete with the provider rewrite |
| `test_settings_router.py::…persists_api_keys…` | `active_service` now added on save | Delete (endpoint not ported) |
| `Settings.test.tsx`, `ServiceSetupModal.test.tsx` | Same `active_service` payload change | Delete (screens being cut) |
| `Quiz.test.tsx` × 4, `Feedback.test.tsx` × 3 | Keyboard-shortcut tests against stale mocks | **Fix**: these encode real behaviour that ports to the web |

### Coverage of code the port touches
`quiz/` + `services/`: **92% line coverage** (800 statements, 197 tests). But both C-2 (guideline_id dropped) and C-5
(f-string prompt) passed the suite, because tests mock the store and the LLM. When porting, write characterisation
tests that go through the real store and assert on the rendered prompt text.

---

## 7. Disclaimer and privacy (draft positions)

**Disclaimer** (shown on first visit, in the footer, and on every feedback screen):

> Study aid only. Not clinical guidance. Questions and marking are generated by AI from the publicly available ACTAS
> Clinical Management Guidelines and may contain errors. Always follow the current CMGs and your service's directions.

**Attribution:** every question and feedback panel shows "Source: ACTAS CMG <number> <title>" with a link to
`cmg.ambulance.act.gov.au`. Citation prefix comes from the service `short_name`, as now.

**Privacy basics for the policy:**
- Data held: email, study history (questions seen, answers, scores), quota counters. No names, no service ID numbers.
- **User answers are sent to the LLM provider for marking.** The policy must name the provider and where it processes data.
- **Do not use the Gemini free tier in production:** Google's pricing page states free-tier data is used to improve its
  products. Use the paid tier.
- GLM is run by Zhipu (Z.ai). Where Z.ai processes API data has not been checked in this review; verify before choosing GLM for marking.
- Offer account deletion that removes history and answers. Keep `usage_ledger` without answer text.
- Pick a D1 location hint near Australia if available (verify in Phase 2).

---

## 8. Cost model

### Token estimates per call (from the current prompts and chunk sizes)

| Call | Input tokens | Output tokens | Basis |
|---|---|---|---|
| Generate (current) | ~3,000 | ~200 | system prompt ~260 + 5 chunks ~2,500 + history |
| Mark (current, 5 chunks) | ~2,900 | ~350 | system ~150 + question + 5 chunks + answer |
| Mark (fixed per H-11, 1–2 chunks) | ~1,000 | ~350 | |

These are estimates from prompt text and chunk caps, not from logs (the app records no usage). Replace with measured
numbers once H-8 is done. "Thinking" tokens are billed as output on Gemini; keep thinking off or minimal for both calls
or output cost can multiply several times over.

### Prices (checked 2026-10-31 against the providers' own pricing pages)

| Model | Input $/M | Output $/M | Batch | Source |
|---|---|---|---|---|
| Gemini 3.8 Flash | 0.75 (1.50 from 2027-01-01) | 3.75 (7.50 from 2027-01-01) | 50% off | ai.google.dev/gemini-api/docs/pricing |
| Gemini 3.5 Flash-Lite | 0.30 | 2.50 | 50% off | same |
| GLM-5.3-Flash | 0.15 | 0.50 | none listed | docs.z.ai/guides/overview/pricing |
| GLM-5.3-FlashX | 0.37 | 1.25 | none listed | same |

Gemini 3.8 Flash's price doubles on 1 January 2027, before any likely launch date, so the 2027 price is used below.

### Cost per call (USD)

| Model | Generate | Mark (current) | Mark (fixed) |
|---|---|---|---|
| Gemini 3.8 Flash (2027) | $0.0060 | $0.0070 | $0.0041 |
| Gemini 3.5 Flash-Lite | $0.0014 | $0.0017 | $0.0012 |
| GLM-5.3-Flash | $0.0006 | $0.0006 | $0.0003 |

### Pre-seeding the bank
About 190 source documents (56 CMG, 98 CSM, 35 MED). At ~8 questions per document per difficulty × 3 difficulties,
plus extra ICP variants, the bank is roughly **5,000 questions**. Batch cost on Gemini 3.8 Flash (2027): about
**$15**. On Flash-Lite: about $3.50. LLM cost is trivial. **The real cost is the clinical spot-check**: a 5% sample
is 250 questions for Oscar to review.

**Size the bank per filter cell.** A user filtering to one guideline at one difficulty sees ~8 questions before the
bank runs dry and live generation starts. Either seed more per guideline for the most-used ones, or allow re-serving
seen questions (spaced repetition) before falling through to generation.

### Monthly spend projection (signed-in users, full quota = 20 generations + 30 marks)

Worst case assumes every user uses their whole quota. Expected case assumes 30% of users are active monthly and use
half their quota, and that 90% of generation requests are served from the bank.

| Users | Worst case, Gemini 3.8 Flash | Expected, Gemini 3.8 Flash | Expected, Flash-Lite | Expected, GLM-5.3-Flash |
|---|---|---|---|---|
| 100 | $33 | $3.30 | $0.80 | $0.30 |
| 1,000 | $330 | $33 | $8 | $3 |
| 10,000 | $3,300 | $330 | $80 | $30 |

Marking dominates (about 95% of expected spend), because it cannot be cached. Fixing H-11 cuts that by roughly 40%.
Anonymous users cost nothing in LLM spend.

**Cloudflare platform:** Workers Paid base plan ($5/month) covers this. D1 stays far below the 10 GB per-database limit.
Vectorize: ~2,000 chunks + 5,000 questions at 768 dimensions is ~5.4M stored dimensions, inside the included 10M.
D1 is single-threaded per database (about 1,000 queries/s at 1 ms each); batch queries in the serve path.

### Quota recommendation
Keep **20 generations / 30 marks** per month. At expected usage the cost is under $0.04 per signed-in user per month on
Gemini 3.8 Flash. Set the global circuit breaker at a fixed monthly spend (e.g. $50 at launch) rather than per-user
numbers. Revisit after the marking benchmark picks a model.

---

## 9. Corrections to the plan

- §1 "What blocks": the `service` column exists in the schema but is never written (H-1).
- §1 hygiene: on `main`, there is no LM Studio provider, no `studyBotcode-archive/`, and no orphan root scripts. Those
  describe Oscar's local working copy. The failing-test counts in the plan (9 + 11) match what I measured; `KNOWN_TEST_FAILURES.md` does not.
- §2 data model: add `primary_chunk_id` and `guideline_checksum` to `question_bank`; drop LLM-chosen `category` in favour of the guideline section.
- §3 Phase 3: the build script must read CSMs and MEDs from the legacy `data/cmgs/structured/` path, or the data must be migrated first (C-3).
- §5 open item 1: the benchmark harness must be pushed before it can be reused (H-7).

## 10. Decisions needed from Oscar (for sign-off)

1. Accept the go/no-go table in §0.
2. Clinical check of AP/ICP tags on mixed-scope medicines (H-9).
3. Push `feature/lmstudio-local-models` (or confirm the benchmark should be rebuilt).
4. Rotate the three local API keys (Phase 0).
5. Confirm the quota numbers (§8) or set a launch spend cap.

### Sign-off (Oscar, 2026-11-01)

Phase 1 is signed off. Phase 2 may start.

1. **Go/no-go table accepted.** The rewrite (Option B), D1 and Vectorize are go. The corpus and prompt no-gos stay as
   preconditions for Phases 3 and 4. Model choice is unblocked (below).
2. **AP/ICP tags:** clinically reviewed and fixed (PRs #5 and #10, `docs/review/actas-scope-tagging.md`).
3. **Benchmark:** done (PR #8, `docs/review/model-bench/README.md`).
4. **API keys:** rotated, and the old keys are revoked.
5. **Quota:** keep the placeholder numbers (20 generations and 30 marks per signed-in user per month). Oscar sets
   provider spend caps to prevent overspend.
6. **Models:** Gemini 3.8 Flash for question generation and bank pre-seeding (batch); Gemini 3.5 Flash-Lite for live
   marking. GLM isn't used.

---

## Appendix A: H-9 medication scope tags for clinical review

Source: `data/services/actas/medications/*.json`. Each medicine carries **one tag on every dose entry**, whatever guideline
the dose comes from. Review each row: is the tag right for every guideline listed?

**Internal contradiction found:** the guideline data marks **CMG 3A RSI** (and 3B Intubation Algorithm) as ICP-only, but
RSI doses for **atropine, ketamine, midazolam, morphine and normal saline** are tagged AP. At minimum those RSI entries
look wrong. Other rows need your judgement.

Not in the index at all: aspirin, droperidol, glucagon, olanzapine, topical anaesthetic (LMX4).

| Medicine | Tag on every entry | Entries | Guidelines the doses come from |
|---|---|---|---|
| Adenosine | ICP | 3 | CMG 8 Tachyarrhythmias |
| Adrenaline | AP | 594 | CMG 12 Upper Airway Obstruction; CMG 14 Shock and Hypoperfusion; CMG 29 Allergic and Anaphylactic Reactions; CMG 38A Meningococcal Disease; CMG 38 Sepsis; CMG 39 Major Trauma; CMG 4A ROSC: Adult (Return of Spontaneous Circulation); CMG 4 Cardiac Arrest: Adult; CMG 5 Cardiac Arrest: Paediatric (<12 years old); CMG 7 Bradyarrhythmias; CMG 9 Respiratory Distress |
| Amiodarone | ICP | 84 | CMG 4 Cardiac Arrest: Adult; CMG 5 Cardiac Arrest: Paediatric (<12 years old); CMG 8 Tachyarrhythmias |
| Atropine | AP | 12 | CMG 35A Poisoning and Overdose; CMG 35B Bites and Stings; CMG 3A RSI (Rapid Sequence Intubation); CMG 7 Bradyarrhythmias |
| Calcium Chloride | AP | 1 | CMG 27 Hyperkalaemia |
| Ceftriaxone | AP | 6 | CMG 38A Meningococcal Disease |
| Fentanyl | AP | 1 | CMG 2 Pain Management |
| Glucose | AP | 30 | CMG 10 Diabetic Emergencies; CMG 1 General Care |
| Glyceryl Trinitrate | AP | 2 | CMG 18A Autonomic Dysreflexia |
| Gtn | AP | 9 | CMG 18A Autonomic Dysreflexia; CMG 2 Pain Management; CMG 9 Respiratory Distress |
| Heparin | ICP | 10 | CMG 16 Suspected ACS (Acute Coronary Syndrome); CMG 28 Home Dialysis Emergencies |
| Hydrocortisone | ICP | 4 | CMG 43 Adrenal Crisis; CMG 9 Respiratory Distress |
| Ibuprofen | AP | 8 | CMG 2 Pain Management; CMG 44 Febrile Paediatric (<12yo) |
| Ipratropium | AP | 1 | CMG 9 Respiratory Distress |
| Ketamine | AP | 57 | CMG 2 Pain Management; CMG 37 Combative and Agitated Patients; CMG 3A RSI (Rapid Sequence Intubation) |
| Levetiracetam | ICP | 2 | CMG 22 Seizures |
| Lignocaine | ICP | 6 | CMG 8 Tachyarrhythmias |
| Magnesium | AP | 124 | CMG 26C Other Obstetric and Gynaecological Emergencies; CMG 4 Cardiac Arrest: Adult; CMG 5 Cardiac Arrest: Paediatric (<12 years old); CMG 8 Tachyarrhythmias |
| Methoxyflurane | AP | 6 | CMG 26A Unscheduled Normal Field Birth; CMG 2 Pain Management |
| Midazolam | AP | 105 | CMG 22 Seizures; CMG 37 Combative and Agitated Patients; CMG 3A RSI (Rapid Sequence Intubation); CMG 3 Airway Management; CMG 45 Palliative Care and VAD |
| Morphine | AP | 42 | CMG 2 Pain Management; CMG 3A RSI (Rapid Sequence Intubation); CMG 45 Palliative Care and VAD |
| Naloxone | AP | 2 | CMG 35A Poisoning and Overdose |
| Normal Saline | AP | 132 | CMG 28 Home Dialysis Emergencies; CMG 39 Major Trauma; CMG 3A RSI (Rapid Sequence Intubation); CMG 5 Cardiac Arrest: Paediatric (<12 years old) |
| Ondansetron | AP | 4 | CMG 20 Eye Emergencies; CMG 41 Nausea and Vomiting |
| Oxygen | AP | 1344 | CMG 12 Upper Airway Obstruction; CMG 14 Shock and Hypoperfusion; CMG 15 Altered Level of Consciousness; CMG 16 Suspected ACS (Acute Coronary Syndrome); CMG 17 Chest Injuries; CMG 18 Spinal Injuries; CMG 1 General Care; CMG 21 Burns; CMG 22 Seizures; CMG 24 Drowning; CMG 25 Diving Emergencies; CMG 26C Other Obstetric and Gynaecological Emergencies; CMG 28 Home Dialysis Emergencies; CMG 29 Allergic and Anaphylactic Reactions; CMG 30 Crush Syndrome; CMG 35A Poisoning and Overdose; CMG 37 Combative and Agitated Patients; CMG 39 Major Trauma; CMG 3A RSI (Rapid Sequence Intubation); CMG 3B Intubation Algorithm; CMG 3C Preexisting Tracheostomy Management; CMG 3 Airway Management; CMG 41 Nausea and Vomiting; CMG 4 Cardiac Arrest: Adult; CMG 5B Neonate Resuscitation; CMG 5 Cardiac Arrest: Paediatric (<12 years old); CMG 7 Bradyarrhythmias; CMG 9 Respiratory Distress |
| Paracetamol | AP | 6 | CMG 2 Pain Management; CMG 44 Febrile Paediatric (<12yo) |
| Prochlorperazine | AP | 3 | CMG 41 Nausea and Vomiting |
| Salbutamol | AP | 2 | CMG 27 Hyperkalaemia; CMG 9 Respiratory Distress |
| Sodium Bicarbonate | ICP | 120 | CMG 27 Hyperkalaemia; CMG 35A Poisoning and Overdose; CMG 4 Cardiac Arrest: Adult; CMG 5 Cardiac Arrest: Paediatric (<12 years old) |
| Suxamethonium | ICP | 18 | CMG 3A RSI (Rapid Sequence Intubation) |
