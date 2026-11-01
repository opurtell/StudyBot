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
- **Recommendation (pending the question rating):** Gemini 3.5 Flash-Lite for marking and generation. It's
  4× cheaper and 4× faster than 3.8 Flash at the same marking accuracy. Keep 3.8 Flash as the fallback,
  or use it for pre-seeding the bank if its questions rate better.

## Caveats

- Small labelled set (10 graded answers). It's enough to rule GLM out, but not to separate the two Gemini models.
- Costs are estimated from characters / 4, because the LLM interface doesn't return token usage yet (H-8).
- Questions were generated with the current prompt, which includes the C-5 citation bug, so ignore the
  `citation` column.
