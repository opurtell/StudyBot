# Question quality scorer: calibration (2026-11-17)

`src/python/web_corpus/quality.py` scores web bank questions with a local LM Studio model. Calibrated on
`sample-labels.csv` (150 questions rated strong / acceptable / weak), split stratified by label into 99 tune and 51
holdout. Target: catch at least 80% of weak, flag at most 10% of strong.

| Model | Split | Weak caught | Acceptable flagged | Strong flagged |
|-------|-------|-------------|--------------------|----------------|
| openai/gpt-oss-20b (original prompt) | tune | 0.17 | - | - |
| openai/gpt-oss-20b (best of two rewrites) | tune | 0.61 | - | 0.18 |
| qwen/qwen3.8-27b | tune | 0.83 | 0.30 | 0.08 |
| qwen/qwen3.8-27b | holdout (run once) | **0.50** | 0.40 | 0.065 |

- gpt-oss-20b ignored explicit rubric rules (with `reasoning_effort: none`).
- qwen3.8-27b follows the rubric but takes about 25 s a question: 24 to 30 hours for the full bank.
- Most holdout misses sat at relevance 3 with no trivia label, the borderline band between weak and strong.
- The "scenario does not change a list answer" rule was dropped during tuning (no gain on tune); it would have caught
  one holdout miss.

Outcome: the holdout missed the weak target, and Oscar chose not to run the full bank. The bank is unchanged. Options
for a later attempt: rate more questions for a larger, less noisy test set, or accept the rubric and rely on the
`review.csv` rescue step.
