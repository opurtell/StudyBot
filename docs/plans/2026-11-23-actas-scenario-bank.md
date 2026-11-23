# Scenario bank plan (web app, ACTAS first)

*Status: plan for review, 2026-11-23. Nothing here is built yet.*

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
- **Pilot size:** 10 guidelines x 3 difficulties = 30 scenarios (AP view). Full bank target: about 300 (roughly 5 per
  CMG, weighted), plus ICP-only scenarios for the ICP-heavy guidelines (cardiac arrest, ROSC, arrhythmias, airway).

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
- **Oscar reviews every scenario in the pilot and the first full run.** Scenarios are longer and riskier than single
  questions, and 300 is a manageable read. Rejections and notes are written back to `review.csv`; only approved rows
  get `reviewed_by` / `reviewed_at` and are exported. Later top-ups can move to sampling once the reject rate is known.

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
| 1. Pipeline + schema | `scenarios.py` (plan, write, check, export, review.html), tests, migration 0009, Worker read routes | Cloud thread, PR | Tests pass; pilot of 30 generated, Oscar reviews all |
| 2. Admin-only release | UI behind an admin flag; pilot loaded to production | PR, deploy | Oscar and a few testers complete pilot scenarios; no accuracy reports |
| 3. Public release | Full run (~300 AP + ICP-only set), Oscar reviews, load, flag off | Mac, then deploy | Bank live; watch reports and completion for two weeks |
| 4. Extensions | AI stage marking, mastery integration, patient-group filter, AT scenarios via the service registry | Later | Each is its own PR |

Rough effort: Phase 0 one session; Phase 1 two to three PRs; Phase 2 one PR plus mock-ups; Phase 3 about 6 hours of
writing plus about 3 to 4 hours of checking for 300 scenarios (overnight on the Mac), confirmed in Phase 0.

## 12. Risks

| Risk | Mitigation |
|---|---|
| Invented vitals that point to a different pathway than the rubric | Prompt rule + checker question 3 + Oscar's full review |
| Model writes plausible doses not in the source | Line-id citations, number-in-cited-lines check, reference cards for weight bands |
| ICP content leaking to AP users | All-sources visibility rule + `icpMentionPattern` + Worker re-check |
| Small local model can't hold a multi-document pack | Bench in Phase 0; cap the pack (primary guideline + up to 2 linked docs); split long CMGs by heading |
| Bank skews to long guidelines again | Importance-weighted quotas file, reviewed by Oscar |
| Self-marking is generous | Critical points, highlighted source lines, AI marking later |

## 13. Decisions and open questions

Settled (Oscar, 2026-11-23):

- **Skill set means scope of practice:** AP, ICP, ICP only, plus PACER.
- **Writer model:** Inkling 2 Mini, subject to the Phase 0 writing check. Benchmarks are in `~/claudeCode/onthismac/localai/`.

Open:

1. **Review load:** happy to review all ~300 scenarios before public release, or sample after the pilot?
2. **Quota weights:** which guidelines matter most for scenarios (a first draft of `scenario_quotas.tsv` will be
   proposed from the CMG list for Oscar to edit).
