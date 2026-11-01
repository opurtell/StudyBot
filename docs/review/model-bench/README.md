# Cloud model benchmark (web port Phase 1, slice 4)

**Run:** 2026-11-01 on Oscar's Mac with `scripts/bench-cloud-models.py --generate 50`.
**Raw output:** `results.json`. **Question sample:** `question-sample.csv` (all 3 models, 150 rows) and
`question-sample-top2.csv` (the two Gemini models, 100 rows). `question-sample-key.json` names the model
behind each code. Don't open it until the rating is done.

## Marking

Labelled set: 10 answers with a known grade (5 incorrect, 3 partial, 2 correct), plus 10 quote-grounding cases.

| Model | JSON | Grading | Incorrect | Partial | Correct | Fabricated credit | Grounded quotes | Median / max | USD per mark |
|---|---|---|---|---|---|---|---|---|---|
| Gemini 3.8 Flash | 20/20 | **10/10** | 5/5 | 3/3 | 2/2 | **0** | **8/10** | 6.1 s / 7.8 s | 0.0035 |
| Gemini 3.5 Flash-Lite | 19/20 | **10/10** | 5/5 | 3/3 | 2/2 | **0** | 7/10 | **1.5 s / 2.0 s** | 0.0008 |
| GLM-5.3-Flash | 20/20 | 9/10 | 5/5 | 3/3 | 1/2 | 2 | 6/10 | 19.3 s / 38.1 s | 0.0003 |
| GLM-5.3-FlashX | not run | | | | | | | | |

GLM-5.3-FlashX was refused: the Z.ai coding plan key doesn't include it (error 1311). The pay-as-you-go
Z.ai key has no credit.

## Generation (50 questions each, same sources: 34 AP, 16 ICP, mixed difficulty)

| Model | Generated | Failures | Exact duplicates | Median | USD per question |
|---|---|---|---|---|---|
| Gemini 3.8 Flash | 50 | 0 | 0 | 7.6 s | 0.0016 |
| Gemini 3.5 Flash-Lite | 50 | 0 | 0 | 1.2 s | 0.0004 |
| GLM-5.3-Flash | 50 | 0 | 0 | 12.7 s | 0.0001 |

Automated scope check: none of the 102 AP-level questions names an ICP-only medicine or says "ICP".
Clinical accuracy and usefulness still need Oscar's rating.

## Reading

- **Both Gemini models mark perfectly** on the labelled set, with no fabricated credit. 3.8 Flash grounds
  quotes slightly better (8/10 vs 7/10). Single-run differences of a point are noise.
- **GLM-5.3-Flash credited two wholly wrong answers** and marked a correct answer down. It's also the slowest
  (median 19 s). For a study tool, made-up credit is the worst failure, because it hides a knowledge gap.
- **Recommendation:** see "Decision" below.

## Oscar's rating (2026-11-01, `question-sample-top2.csv`, 100 rows)

M1 = Gemini 3.5 Flash-Lite, M2 = Gemini 3.8 Flash.

| Model | Accurate | Useful (mean, 1 to 5) | Rated 1 | AP-level questions out of AP scope |
|---|---|---|---|---|
| Gemini 3.8 Flash | **48/50** | **3.96** | 2 | 0/34 |
| Gemini 3.5 Flash-Lite | 45/50 | 3.65 | 5 | 1/34 |

The "in scope" column marked 17 ICP-level rows N with "is AP scope". This isn't a fault. An ICP-level row is a
question for an ICP user, whose scope includes all AP content, so AP material is expected there. The sheet
labelled the column ambiguously.

Causes of the inaccurate or 1-rated questions:
1. **The question doesn't name the medicine** (droperidol, calcium chloride, levetiracetam; 5 rows across both
   models). The chunk came from the middle of a monograph, so the drug name wasn't in the text. **Fixed:** every
   ACTAS chunk now starts with a `[ACTAS MED 08: Droperidol (Droleptan)]` style header.
2. **The answer wasn't in the excerpt** (hyperkalaemia; 2 rows). The chunk was cut before the answer. The bank
   build should keep sections whole or store neighbouring chunks.
3. **Illogical or self-answering questions** (2 rows, both Flash-Lite).
4. **One AP scope leak** (CMG 4A, external pacing). This is a tagging gap, not the model. **Fixed:** guideline
   lines that name external pacing are now ICP.
5. **Too wordy** at hard difficulty (4 notes). Tune the hard-difficulty prompt in the port.

Source errors Oscar spotted (CSM.P03 buttock side, CSM.C04 adult pad placement) are logged in `InfoERRORS.md`.

## Decision

- **Question generation (bank pre-seeding): Gemini 3.8 Flash.** It's more accurate and more useful. It runs
  offline in batch, so its speed doesn't matter, and the cost is about $8 for a 5,000-question bank at batch prices.
- **Live marking: Gemini 3.5 Flash-Lite.** It marks the same as 3.8 Flash (10/10, no fabricated credit), and
  it's 4× faster and 4× cheaper. Users wait on this call.
- **GLM-5.3-Flash: not used.** It credited wrong answers.

## Caveats

- Small labelled set (10 graded answers). It's enough to rule GLM out, but not to separate the two Gemini models.
- Costs are estimated from characters / 4, because the LLM interface doesn't return token usage yet (H-8).
- Questions were generated with the current prompt, which includes the C-5 citation bug, so ignore the
  `citation` column.
