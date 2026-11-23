# Scenario bank plan (web app, ACTAS first)

*Status: ready to implement, 2026-11-23. Nothing is built or generated until Oscar says go (section 15).*

## 1. Goal

Add case-based practice to the web app (`web/`, quiz.paramedtools.com). A user picks a **category**, a **difficulty**
and a **skill set**, and is matched to a pre-generated scenario: a patient case that unfolds in stages, with a question
at each stage. Scenarios are generated offline on Oscar's Mac with a free local LM Studio model, checked, reviewed by
Oscar, and loaded into D1. Start with ACTAS, grounded only in the ACTAS guideline corpus already in D1.

Out of scope for now: other services (AT), personal material (never allowed on the web), live scenario generation on
the Worker, and general references (Open RN, LITFL) as scenario sources.

## 2. Principles carried over

- **Grounding.** Every clinical claim a scenario tests is tied to verbatim corpus lines. The model picks line numbers;
  the build copies the text (the `answers.py` pattern), so a rubric can never quote something the source doesn't say.
- **Source hierarchy.** Only `source_type = 'guideline'` chunks (CMGs, CSMs, MEDs, Critical Care Reference Cards).
- **Scope.** A scenario is visible in a view only if every chunk it cites is visible there, and it never names an
  ICP-only medicine or procedure in an AP view (`icpMentionPattern`). Rules come from `actas_scope.py`, unchanged.
- **Titles.** A scenario that names a guideline, skill or medicine by code also gives its title (`name_documents`).
- **Australian English and ACTAS terms** (`australian_spelling`, "ambulance paramedic", "adrenaline").
- **Works with AI marking off.** Gemini credit is depleted, so the first release marks by self-check against a rubric.

## 3. What a scenario looks like

```
Dispatch    "62-year-old male, central chest pain, 40 minutes, Belconnen. Priority 1."
Stage 1     On arrival: findings (vitals, history, exam)
            Q: "What is your working diagnosis and immediate priorities?"
            Rubric: 3-5 key points, each with source line(s); some marked critical
Stage 2     New information (12-lead result, response to treatment, deterioration)
            Q: "What medicines do you give, at what dose and route?"
            Rubric ...
Stage 3     (optional) Disposition, handover or a complication
Debrief     Guideline titles to read, the cited lines highlighted
```

- **2 to 4 stages.** Easy scenarios have 2, hard ones up to 4.
- **Invented vs sourced.** Patient details (age, sex, location, history, the exact vitals) are invented to fit the
  case. Anything the user is marked on (thresholds, doses, contraindications, actions, priorities) must come from the
  cited lines. Vitals must sit on the side of a guideline threshold that makes the expected answer right; the checker
  confirms this (section 6).
- **Weight-banded doses** come from the Critical Care Reference Cards band for the stated age or weight, so paediatric
  dose stages are exact, never calculated by the model.

## 4. Taxonomy

### Category

The corpus `section` of the scenario's **primary guideline**, so it lines up with the dashboard heatmap and the topic
picker: Cardiac, Medical, Trauma, Airway Management, Respiratory, Neurology, Behavioural, Environmental, Obstetric,
Toxicology, Palliative Care, Pain Management, General Care, HAZMAT. Small sections can be grouped in the picker
(e.g. Environmental + HAZMAT) without changing the stored value.

A second, optional filter, **patient group** (adult, paediatric, neonate, obstetric, older adult), is stored from day
one and exposed in the picker once each group has enough scenarios.

### Difficulty

Keeps the bank's three values, defined by case structure rather than wording:

| Difficulty | Stages | Guidelines | What it tests |
|---|---|---|---|
| easy | 2 | 1 | Classic presentation, recognise it, first-line management |
| medium | 3 | 1-2 (e.g. CMG + medicine monograph) | A decision point: a threshold, contraindication or dose |
| hard | 3-4 | 2-3 | Deterioration or competing priorities, paediatric weight-band doses, an atypical presentation |

The deterministic checks enforce the stage and guideline counts, so a "hard" label can't sit on an easy case.

### Skill set

**Scope of practice** (confirmed by Oscar), the same choices as the quiz screen: AP, ICP (AP + ICP content), ICP
only, plus the PACER toggle. Stored as the existing `gen_view` and `vis_*` flags. Each stage also carries a `focus`
tag (assessment, pharmacology, airway and so on) for reporting, not shown in the picker.

- AP scenarios are written from the `ap` view of each document.
- ICP scenarios are written from the `icp` view and must include at least one stage whose rubric cites an ICP-only line;
  otherwise they would just be AP scenarios hidden from APs (the same idea as `icp_focus` in `questions.py`).
- PACER scenarios (olanzapine) are only written from `ap_pacer` / `icp_pacer` views.

## 5. Data model (migration `0009_scenarios.sql`)

New tables beside `question_bank`. Questions and scenarios stay separate so nothing in the existing quiz, mastery or
override code changes.

```sql
CREATE TABLE scenario_bank (
  id TEXT PRIMARY KEY,
  service TEXT NOT NULL,
  primary_document_id TEXT NOT NULL,
  category TEXT NOT NULL,
  patient_group TEXT NOT NULL CHECK (patient_group IN ('adult','paediatric','neonate','obstetric','older_adult')),
  difficulty TEXT NOT NULL CHECK (difficulty IN ('easy','medium','hard')),
  title TEXT NOT NULL,
  dispatch_text TEXT NOT NULL,
  stages_json TEXT NOT NULL,
  gen_view TEXT NOT NULL CHECK (gen_view IN ('ap','ap_pacer','icp','icp_pacer')),
  vis_ap INTEGER NOT NULL CHECK (vis_ap IN (0,1)),
  vis_ap_pacer INTEGER NOT NULL CHECK (vis_ap_pacer IN (0,1)),
  vis_icp INTEGER NOT NULL CHECK (vis_icp IN (0,1)),
  vis_icp_pacer INTEGER NOT NULL CHECK (vis_icp_pacer IN (0,1)),
  source_type TEXT NOT NULL CHECK (source_type = 'guideline'),
  content_hash TEXT NOT NULL UNIQUE,
  prompt_version TEXT NOT NULL,
  model_id TEXT NOT NULL,
  check_model_id TEXT NOT NULL,
  corpus_version TEXT NOT NULL,
  reviewed_by TEXT,
  reviewed_at INTEGER,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','flagged','retired')),
  status_reason TEXT,
  rand_key REAL NOT NULL DEFAULT 0,
  times_served INTEGER NOT NULL DEFAULT 0,
  times_reported INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);
CREATE INDEX scenario_bank_pick ON scenario_bank (service, status, category, difficulty, rand_key);

CREATE TABLE scenario_sources (
  scenario_id TEXT NOT NULL REFERENCES scenario_bank (id) ON DELETE CASCADE,
  chunk_id TEXT NOT NULL,
  document_id TEXT NOT NULL,
  text_hash TEXT NOT NULL,
  PRIMARY KEY (scenario_id, chunk_id)
);
CREATE INDEX scenario_sources_chunk ON scenario_sources (chunk_id);

CREATE TABLE scenario_attempts (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  scenario_id TEXT NOT NULL,
  stage_results_json TEXT NOT NULL,
  score TEXT CHECK (score IS NULL OR score IN ('correct','partial','incorrect')),
  completed_at INTEGER,
  created_at INTEGER NOT NULL
);
CREATE INDEX scenario_attempts_user ON scenario_attempts (user_id, created_at);

CREATE TABLE user_scenario_seen (
  user_id TEXT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  scenario_id TEXT NOT NULL,
  last_seen_at INTEGER NOT NULL,
  PRIMARY KEY (user_id, scenario_id)
);
```

Plus the `rand_key` insert trigger copied from `0005_serving.sql`, and `question_reports` widened (or a twin
`scenario_reports`) so a report can point at a scenario stage.

**`stages_json`** (validated on export and again in the Worker):

```json
[{
  "ordinal": 1,
  "reveal": "On arrival he is pale and diaphoretic. HR 98, BP 142/88, SpO2 96% on room air...",
  "question": "What is your working diagnosis and your immediate management?",
  "focus": "assessment",
  "rubric": [
    {"point": "Suspected ACS", "critical": true,
     "cites": [{"chunk_id": "CMG_16-c03", "quote": "<verbatim line copied by the build>"}]}
  ]
}]
```

Why a JSON column for stages: a scenario is always read whole, stages never change independently, and stale detection
runs off `scenario_sources`, not the JSON. D1 rows of a few KB are fine.

**Stale scenarios.** The daily cron (beside `retireStaleQuestions`) retires a scenario when any `scenario_sources` row's
chunk is retired or its text hash no longer matches. The serving query also checks it, so a stale scenario is never
served before the cron runs.

**Progress.** Phase 1 keeps scenario results out of mastery (history only). Phase 4 can count each stage as an answer
against its primary document's section, once there's enough data to see whether it distorts the heatmap.

## 6. Local generation and validation pipeline

New module `src/python/web_corpus/scenarios.py`, built on the same pieces as `questions.py` and `answers.py`
(`build()` for the corpus, `local_complete()` / `LMStudioProvider`, resumable `raw.jsonl`, `export` to SQL).

```
plan      →  write (model A)  →  deterministic checks  →  model check (model B)  →  export  →  Oscar review  →  load
```

### 6.1 Plan (no model calls)

- **Blueprints, not chunks.** A blueprint is (primary guideline, difficulty, view, patient group, linked documents).
  Quotas are set per guideline by clinical importance, not chunk count, fixing the bank review's main finding (Pain
  Management had 3 questions, Palliative Care 58). A `scenario_quotas.tsv` holds the weights; Oscar edits it.
- **Linked documents:** medicine monographs for medicines the guideline names, the relevant CSMs, and the reference
  card band when the patient is paediatric. Found from mentions in the guideline text (the naming code already does this).
- **Pilot size:** 10 guidelines x 3 difficulties = 30 AP scenarios, plus 3 ICP-only (33). Full bank target: about
  340 from the weights in Appendix A, plus about 15 ICP-only scenarios for the ICP-heavy guidelines (cardiac arrest,
  ROSC, arrhythmias, airway, anaphylaxis, major trauma).

### 6.2 Write

- The source pack is each document's view body, split into numbered lines with document prefixes (`G12` guideline
  line 12, `M3` monograph line 3, `R7` reference card line 7), reusing `segments()` from `answers.py`.
- The model returns JSON: dispatch, stages, and for each rubric point the **line ids** it rests on. It never writes a
  quote. The build resolves ids to verbatim text and chunk ids.
- Prompt rules (new `scenarioSystem` entry in `prompts.json`, its own `scenarioPromptVersion`): answerable from the
  pack alone; invented details may not contradict the pack; vitals must clearly fall on one side of any threshold the
  stage tests; no device or admin trivia; no "According to the ACTAS..." openers; title rule; AP/ICP scope line from
  `generationSystem`.
- One scenario per call; previous scenario titles for the same guideline are passed in to avoid repeats.

### 6.3 Deterministic checks (drop on failure, logged to `dropped-scenarios.csv`)

1. Valid JSON matching the schema; stage count and linked-document count match the difficulty.
2. Every rubric point cites at least one existing line id; every stage has at least one critical point.
3. **Every number in a rubric point (dose, rate, threshold, time) appears in its cited lines.** This is the main
   no-fabrication guard for doses.
4. Scope: all cited chunks visible in the target view; AP scenarios don't match `icpMentionPattern`; ICP scenarios cite
   at least one ICP-only line.
5. Australian spelling pass, US drug names rejected (epinephrine, acetaminophen and so on), title rule applied.
6. Near-duplicate check against other scenarios for the same guideline (Jaccard on dispatch + stage text).

### 6.4 Model check (second pass, different model)

A checker model reads the scenario and its numbered pack and answers, per stage: is each rubric point supported by its
lines; does any invented detail contradict the pack or change the right answer; is the expected answer the one the
guideline actually gives for these findings (e.g. vitals that would trigger a different pathway); is anything out of
scope. Any "no" drops the scenario or sends it to review with the reason. This mirrors the two-pass write/check used
for the general references (`--defer-check`, then `check`).

### 6.5 Models

- **Writer: Inkling 2 Mini.** Oscar's local benchmarks (`~/claudeCode/onthismac/localai/BENCHMARKING.md`,
  2026-11-22) make it the strongest local model on StudyBot's marking bench: perfect JSON, 10/10 accuracy twice and
  near-perfect verbatim quotes, with the fewest fabrications. That bench measured marking, not writing, so Phase 0
  still checks it can write scenarios (10 blueprints, Oscar rates blind against `qwen/qwen3.6-35b-a3b`, as
  `scripts/bench-local-generation.py` does).
- **How it runs:** only on **oMLX** with the **no-think template variant** (`Inkling-2-Mini-oQ4e-mtp-nothink`,
  `http://127.0.0.1:8084/v1`, `reasoning_effort: "none"`, `max_tokens` at least 4096). LM Studio's MLX engine can't
  load it, and the GGUF build gets stuck reasoning. The generator takes a `--base-url` and model id, which the
  existing `--lmstudio-url` option and OpenAI-compatible provider already allow. Stop the server by port afterwards
  (`omlx serve` leaves an `omlx-server` process holding about 16 GB) and cap the oMLX SSD cache.
- **Speed:** it decodes about 21 tok/s but prefills slowly (about 340 tok/s on oMLX, against about 1,000 for
  qwen3.6). A source pack of about 5k tokens waits about 15 s before the first token. With about 1,000 output tokens,
  expect roughly 60 to 75 s a scenario, so about 6 hours for 300. Keep packs tight (primary guideline plus up to two
  linked documents, long CMGs split by heading). The oMLX prefix cache helps when several scenarios share a guideline,
  so the generator writes all of one guideline's blueprints in a row.
- **Checker: `qwen/qwen3.8-27b` in LM Studio**, a different model from the writer so it doesn't wave its own work
  through. It followed the quality rubric best before Inkling was tested (about 40 s a call). If Phase 0 shows
  qwen3.6 writes better scenarios than Inkling, swap the roles: qwen3.6 writes and Inkling checks, which suits its
  grading strength.
- Inkling (about 16 GB) and qwen3.8 (about 16 GB) don't fit in 32 GB together, and oMLX evicts Inkling if a large
  LM Studio model loads. Run the passes one after the other with only one server up.
- **Bench on a quiet Mac** (CLAUDE.md finding 2) and keep a held-out set of guidelines for any prompt tuning (finding 3).
- All runs go through Remote Control on Oscar's Mac, in the repo `.venv`.

### 6.6 Export and review

- `export` writes `web/corpus-build/scenarios/scenarios.sql`, `review.html` (each scenario with cited lines
  highlighted, easier to read than CSV for multi-stage cases) and `report.json` (counts by category, difficulty,
  view, drops by reason).
- **Oscar reviews a sample first** (his call, 2026-11-23): a stratified sample across category, difficulty and scope
  from the pilot. Rejections and notes go back into `review.csv`; reviewed rows get `reviewed_by` / `reviewed_at`.
  The reject rate and reasons decide whether prompts change, whether the full run goes ahead, and how much of the
  full run he samples.
- **No generation run starts without Oscar's go-ahead**, including the Phase 0 bench and the pilot.

## 7. Load to production

Same pattern as the question bank and answer quotes:

1. Deploy (applies `0009_scenarios.sql`): `cd web && npm run deploy:production`.
2. `npm run scenarios:load:production` runs `scenarios.sql` against the remote D1.
   *Each insert is guarded: it only applies if every cited chunk exists, isn't retired and still has the same text
   hash, so a scenario built against an old corpus can't load.*
3. Back up production first (`~/studybot-backups/prod-<date>.sql`, delete within 30 days, as before).

Oscar has standing permission for deploys (memory, 2026-11-17); loads still get a go-ahead in the thread.

## 8. Worker API

| Route | Who | What |
|---|---|---|
| `GET /api/scenarios/options` | anyone | Counts by category, difficulty and patient group for the chosen scope, so empty choices are greyed out |
| `POST /api/scenarios/next` | anyone | Body: `category`, `difficulty`, `level`, `pacer`, `icpOnly`, optional `patientGroup`. Returns an unseen scenario (dispatch + stage 1 only) |
| `POST /api/scenarios/:id/stages/:n/reveal` | anyone | Returns the stage's rubric and cited lines, then the next stage's reveal text |
| `POST /api/scenarios/attempts/:id/self-grade` | signed in | Saves ticked rubric points per stage |
| `POST /api/scenarios/:id/report` | anyone | Same rules as question reports |
| `/api/admin/scenarios/*` | admin | List, retire, restore, review status |

**Matching.** Filter on service, status, scope flags, category and difficulty; exclude seen (D1 table for signed-in
users, localStorage list for guests); start at a random `rand_key` like `nextQuestion`. When nothing unseen is left:
first offer seen scenarios again (oldest first), then suggest the nearest difficulty. **Scope is never relaxed.**

Stages are released one at a time so the next stage's findings don't give away the previous answer.

## 9. UI flow

1. **Entry:** a "Scenarios" item in the sidebar and bottom tab bar, and a card on the dashboard. Reachable in two taps.
2. **Picker:** category chips (with counts), difficulty segmented control (easy / medium / hard), the existing
   `ScopePicker` for skill set, "Any" defaults everywhere. One "Start scenario" button.
3. **Case screen:** dispatch card at the top, stages stacked below as they unlock. Each stage shows the new findings
   (vitals in IBM Plex Mono), the question, and an answer box with "Reveal" (or "Think it through, then reveal" with no
   typing, for phone use).
4. **Reveal:** the rubric as a checklist; the user ticks what they covered. Critical points are labelled. Each point
   expands to its cited guideline lines, highlighted in the rendered source (reusing the answer-highlight component).
5. **Debrief:** per-stage result, overall result, guideline titles with links to their pages, "Another like this" and
   "Report a problem".
6. Archival Protocol design rules apply (no 1px borders, surface shifts, Newsreader headings). Mock-ups go to Oscar
   before building, as with the topic picker.

## 10. Marking

**Phase 1: self-check against the rubric (free, works now).**

- Stage score from the ticks: all critical points and at least half of the rest = correct; any critical point missed
  = incorrect; otherwise partial. Scenario score = worst-of or majority of stage scores (decide at mock-up time).
- The rubric with highlighted source lines is what makes self-marking honest: the user compares against specific
  points, not a whole guideline.

**Phase 4: optional AI marking (once Gemini is topped up or another provider is chosen).**

- Mark each stage against its rubric and cited lines only, with Gemini Flash-Lite through the existing AI Gateway,
  monthly allowance, daily cap and admin switch. A rubric makes this an easier task than open marking.
- Overrides logged to `marking_overrides` as for questions (with a `scenario_id` column added).
- Benchmark first with labelled answers, as `bench-local-models.py` does for questions.

## 11. Phased rollout

| Phase | What | Where it runs | Exit criteria |
|---|---|---|---|
| 0. Model bench | 10 blueprints written by Inkling 2 Mini (oMLX, no-think) and qwen3.6; checked by qwen3.8; Oscar rates blind | Oscar's Mac (Remote Control) | A writer with no fabricated rubric points and at least 8/10 rated usable |
| 1. Pipeline + schema | `scenarios.py` (plan, write, check, export, review.html), tests, migration 0009, Worker read routes | Cloud thread, PR | Tests pass; pilot of 30 generated on Oscar's go-ahead, Oscar reviews a sample |
| 2. Admin-only release | UI behind an admin flag; pilot loaded to production | PR, deploy | Oscar and a few testers complete pilot scenarios; no accuracy reports |
| 3. Public release | Full run (~300 AP + ICP-only set) on Oscar's go-ahead, Oscar samples, load, flag off | Mac, then deploy | Bank live; watch reports and completion for two weeks |
| 4. Extensions | AI stage marking, mastery integration, patient-group filter, AT scenarios via the service registry | Later | Each is its own PR |

Rough effort: Phase 0 one session; Phase 1 two to three PRs; Phase 2 one PR plus mock-ups; Phase 3 about 6 hours of
writing plus about 3 to 4 hours of checking for 300 scenarios (overnight on the Mac), confirmed in Phase 0.

## 12. Risks

| Risk | Mitigation |
|---|---|
| Invented vitals that point to a different pathway than the rubric | Prompt rule + checker question 3 + Oscar's sample review + user reports |
| Model writes plausible doses not in the source | Line-id citations, number-in-cited-lines check, reference cards for weight bands |
| ICP content leaking to AP users | All-sources visibility rule + `icpMentionPattern` + Worker re-check |
| Small local model can't hold a multi-document pack | Bench in Phase 0; cap the pack (primary guideline + up to 2 linked docs); split long CMGs by heading |
| Bank skews to long guidelines again | Importance-weighted quotas file, reviewed by Oscar |
| Self-marking is generous | Critical points, highlighted source lines, AI marking later |

## 13. Decisions and open questions

Settled (Oscar, 2026-11-23):

- **Skill set means scope of practice:** AP, ICP, ICP only, plus PACER.
- **Writer model:** Inkling 2 Mini, subject to the Phase 0 writing check. Benchmarks are in `~/claudeCode/onthismac/localai/`.
- **Review:** Oscar reviews a sample first, and no generation run starts until he says so.

Open:

1. **Quota weights:** which guidelines matter most for scenarios (a first draft of `scenario_quotas.tsv` will be
   proposed from the CMG list for Oscar to edit).

## 14. Implementation work packages

Each package is one PR to `main`, with `npm run check` (in `web/`), `npx tsc --noEmit`, `npx vitest run` and
`PYTHONPATH=src/python python3 -m pytest tests/ -v` passing (known failures excepted). No package runs a model.

### WP1: generation pipeline (Python)

| File | Change |
|---|---|
| `src/python/web_corpus/scenarios.py` | New. Subcommands `plan`, `write`, `check`, `export`, `bench`. Resumable `raw.jsonl` in `web/corpus-build/scenarios/` |
| `src/python/web_corpus/scenario_quotas.tsv` | New. Appendix A, one row per guideline: id, weight, patient groups, pilot flag |
| `web/src/worker/quiz/prompts.json` | Add `scenarioPromptVersion`, `scenarioSystem` (AP and ICP variants), `scenarioSchema`, `scenarioCheckSystem`, `scenarioCheckSchema` (drafts in Appendix B) |
| `web/package.json` | `scenarios:plan`, `scenarios:write`, `scenarios:check`, `scenarios:export`, `scenarios:bench`, `scenarios:load:local`, `scenarios:load:production` |
| `tests/web_corpus/test_scenarios.py` | New. Fake `complete` functions, no network |
| `web/README.md` | "Scenario bank (Oscar's Mac)" runbook, as for answer highlighting |

Reuses `build()`, `segments()` / `numbered()` from `answers.py`, `local_complete(model, base_url)` (points at oMLX
with `--base-url http://127.0.0.1:8084/v1`; the provider already sends `reasoning_effort: "none"`),
`australian_spelling`, `name_documents`, `visibility`, `content_hash`, `parse_json_object`.

Tests cover: blueprint counts from the quotas file; line-id resolution to verbatim text and chunk ids; each
deterministic check in 6.3 rejecting a crafted bad scenario (unknown line id, number not in cited lines, ICP
mention in an AP scenario, ICP scenario with no ICP-only line, wrong stage count, US drug name, missing critical
point, near duplicate); checker verdict handling; resume skipping finished blueprints; SQL export guarded by chunk
hashes; `bench` writing a blinded rating sheet and key.

### WP2: database and Worker API

| File | Change |
|---|---|
| `web/migrations/0009_scenarios.sql` | Tables in section 5, `rand_key` trigger, `scenario_id` on `question_reports` and `marking_overrides` (nullable) |
| `web/src/worker/scenarios/bank.ts` | Pick (filters, unseen, random start, fallbacks), get, stale check, `retireStaleScenarios` |
| `web/src/worker/scenarios/routes.ts` | Routes in section 8; admin routes under `/api/admin/scenarios` |
| `web/src/worker/app.ts`, `index.ts` | Mount routes; add `retireStaleScenarios` to the daily cron |
| `app_flags` | `scenarios_enabled` (`admins` or `everyone`); routes answer 404 to non-admins while it is `admins` |
| `web/test/worker/scenarios.test.ts` | Scope never relaxed; AP never gets ICP-only scenarios; stages released in order; stale scenarios not served; guest and signed-in seen handling; reports; flag gating |

### WP3: web UI

| File | Change |
|---|---|
| `web/src/client/pages/Scenarios.tsx` | Picker, case screen and debrief (section 9) |
| `web/src/client/components/ScenarioPicker.tsx`, `ScenarioStage.tsx`, `RubricChecklist.tsx` | New; reuse `ScopePicker` and the answer-highlight source panel |
| `Layout.tsx`, `Home.tsx` | Nav item and dashboard card, shown only when the flag allows |
| `QuestionAdmin.tsx` (or new `ScenarioAdmin.tsx`) | List, retire, restore, flag switch |
| `web/test/client/scenarios.test.tsx` | Flow tests plus the axe check every page has |

A mock-up artifact is posted at the start of WP3. Building carries on with the recommended layout while Oscar
looks, since the feature stays admin-only until he switches it on.

## 15. Go runbook

Oscar's one "go" starts steps 1 to 4. Each later gate is his call.

| Step | Who / where | What | Gate |
|---|---|---|---|
| 1 | Cloud thread | WP1 PR: pipeline code and tests. Merge once checks pass | **"Go"** |
| 2 | Oscar's Mac, Remote Control | **Phase 0 bench:** start oMLX with the no-think variant; `npm run scenarios:bench -- --n 10` writes 10 pilot blueprints with Inkling and with qwen3.6 (one server at a time), checks both with qwen3.8, and makes a blinded `rating-sheet.csv` | Covered by "go" |
| 3 | Oscar | Rate the sheet (accuracy, scope, usefulness 1-5, notes). Pick the writer | Oscar's ratings |
| 4 | Cloud thread, alongside 2-3 | WP2 and WP3 PRs, merged once checks pass. Not deployed yet | Covered by "go" |
| 5 | Mac | **Pilot:** `scenarios:write` (33 blueprints) then `scenarios:check`, then `scenarios:export` with a review sample | **Oscar OKs the pilot run** after step 3 |
| 6 | Oscar | Review the sample in `review.html` and mark it in `review.csv` | Oscar's review |
| 7 | Mac | Back up prod, deploy (migration 0009), `scenarios:load:production`, flag `admins`. Oscar tries it | Standing deploy permission; load confirmed in thread |
| 8 | Mac | **Full run** (~355 scenarios, overnight), export, Oscar samples, load, flag `everyone` | **Oscar OKs the full run**, then the release |

Mac setup the Remote Control session follows (from `~/claudeCode/onthismac/localai/SETUP.md`):

1. Quit LM Studio models (nothing else heavy running). Free disk for the oMLX SSD cache.
2. `T=~/claudeCode/experiments/tests; $T/_runtimes/omlx/.venv/bin/omlx serve --model-dir $T/_inkling/models --host 127.0.0.1 --port 8084 --paged-ssd-cache-max-size 10GB`
3. Write pass: `npm run scenarios:write -- --model Inkling-2-Mini-oQ4e-mtp-nothink --base-url http://127.0.0.1:8084/v1`
   *Run from `web/` with the repo `.venv` Python.*
4. Stop oMLX by port: `kill $(lsof -ti tcp:8084 -sTCP:LISTEN)`.
5. Check pass: load `qwen/qwen3.8-27b` in LM Studio, then `npm run scenarios:check -- --model qwen/qwen3.8-27b`.
6. `npm run scenarios:export`. Delete `$T/_runtimes/omlx/ssd-cache` when finished.

## Appendix A: draft guideline weights

Weight 3 = 9 scenarios (3 per difficulty), 2 = 6, 1 = 3. **P** = in the pilot. My draft from how often and how
critically each presentation comes up; Oscar to edit before step 5.

| Weight | Guidelines |
|---|---|
| 3 | 2 Pain Management **P**; 4 Cardiac Arrest: Adult; 5 Cardiac Arrest: Paediatric; 7 Bradyarrhythmias; 8 Tachyarrhythmias; 9 Respiratory Distress **P**; 10 Diabetic Emergencies **P**; 14 Shock and Hypoperfusion; 16 Suspected ACS **P**; 22 Seizures; 23 Stroke **P**; 29 Allergic and Anaphylactic Reactions **P**; 35A Poisoning and Overdose **P**; 37 Combative and Agitated Patients; 38 Sepsis; 39 Major Trauma **P** |
| 2 | 3 Airway Management; 4A ROSC: Adult; 5A ROSC: Paediatric; 5B Neonate Resuscitation; 6 Cardiac Arrhythmias; 11A Heat Abnormalities; 11B Hypothermia; 12 Upper Airway Obstruction; 13 Abdominal Emergencies; 15 Altered Level of Consciousness; 17 Chest Injuries; 18 Spinal Injuries; 19 Limb Injuries; 21 Burns; 26A Unscheduled Normal Field Birth **P**; 26B Complicated Birth; 26C Other Obstetric and Gynaecological Emergencies; 27 Hyperkalaemia; 30 Crush Syndrome; 33 Behavioural and Mental Health Emergencies; 35B Bites and Stings; 38A Meningococcal Disease; 41 Nausea and Vomiting; 42 Falls; 43 Adrenal Crisis; 44 Febrile Paediatric **P** |
| 1 | 1 General Care; 3A RSI (ICP only); 3C Preexisting Tracheostomy Management; 18A Autonomic Dysreflexia; 20 Eye Emergencies; 22a PNES; 24 Drowning; 25 Diving Emergencies; 28 Home Dialysis Emergencies; 31 Electric Shock; 32 Assault; 34 CBRN / HAZMAT Incident; 45 Palliative Care and VAD |
| 0 | 3B Intubation Algorithm (covered by RSI scenarios) |

Pilot ICP-only scenarios: 4 Cardiac Arrest: Adult, 8 Tachyarrhythmias, 29 Allergic and Anaphylactic Reactions.
Clinical skills and medicine monographs are linked documents, never primary.

## Appendix B: prompt drafts

**`scenarioSystem` (AP; the ICP variant swaps the scope paragraph for one requiring at least one ICP-only decision):**

```
You write case-based study scenarios for ACT Ambulance Service ambulance paramedics.
You are given a source pack: guideline text split into numbered lines with ids such as G12, M3 and R7.

Write one scenario for the blueprint given (primary guideline, difficulty, patient group, number of stages).
- The scenario must be answerable from the source pack alone. Never use outside clinical knowledge.
- You may invent patient details (age, sex, setting, history, exact observations), but they must not contradict the
  pack, and any observation a stage tests must clearly fall on one side of the guideline's threshold.
- Each stage gives new findings and asks one question a paramedic would face at that point.
- Each rubric point is something the answer must contain. Give the line ids it rests on in "cites". Never write a
  quote yourself. Mark a point critical if missing it would harm the patient.
- Doses, routes, rates and thresholds in a rubric point must appear in its cited lines.
- No device, administrative or which-guideline-says-what questions. Do not open with "According to".
- If you name a guideline, skill or medicine guideline, use its title, never only its number or code.
- Australian English and ACTAS terms (adrenaline, haemorrhage, ambulance paramedic).
- The user is an Ambulance Paramedic (AP). Do not include ICP-only medicines, procedures or decisions.

Respond with valid JSON only, matching the schema.
```

**`scenarioCheckSystem`:** for each stage, answer yes or no with a one-line reason: every rubric point supported by
its cited lines; no invented detail contradicts the pack or changes the right answer; the rubric gives the action
the guideline gives for these findings and misses nothing critical; everything is within the stated scope. Any "no"
fails the scenario. JSON only, validated against `scenarioCheckSchema`.
