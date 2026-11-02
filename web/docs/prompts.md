# Question generation and marking: spec for the web port

The Python quiz agent (`src/python/quiz/agent.py`) is the reference implementation. Port its behaviour, including
the fixes below, when Phase 4 builds generation and marking in the Worker. Tests that pin this behaviour:
`tests/quiz/test_prompt_fixes.py`.

## Prompts

Port `build_generation_prompt()` and `EVALUATION_SYSTEM_PROMPT` text as they render today. To see the exact
generation prompt for a service and qualification set:

```bash
PYTHONPATH=src/python python3 -c "
from unittest.mock import patch
from services.registry import get_service
from quiz.agent import build_generation_prompt
with patch('services.active.active_service', return_value=get_service('actas')):
    print(build_generation_prompt(frozenset({'AP'})))
"
```

Store a `prompt_version` with every banked question and every mark, and bump it whenever either prompt changes.

**In the web port the prompts live in `web/src/worker/quiz/prompts.json`** (`promptVersion` `web-2`). The Worker and the
offline bank generator (`src/python/web_corpus/questions.py`) both read it, and `tests/web_corpus/test_questions.py`
fails if it drifts from `agent.py`. One deliberate difference: the hard-difficulty instruction adds "Keep the question
itself under 60 words", because Oscar's rating found hard questions too wordy (`docs/review/model-bench/README.md`).

`web-2` (2026-11-02, Oscar's bank review): questions must name a guideline, skill or medicine guideline by its title, not
only its code ("users will not know guidelines or skills by code/number"), and must not ask which guideline holds a fact.
Because models still slip, both paths also rewrite codes deterministically: `name_documents` in the offline export and
`nameDocuments` (`web/src/worker/quiz/naming.ts`) for live questions turn "CMG 31" into "the Electric Shock guideline
(CMG 31)" using the corpus titles. The export also drops "which guideline contains…" questions. Shared cases:
`web/test/fixtures/naming-cases.json`.

Also from that review: a magnesium precaution APs study was shown only to ICPs, because the ICP view of MED 20 packs
its chunks at different boundaries, so the ICP chunk straddled two AP chunks and wasn't recognised as a twin. An ICP-only
chunk whose text is at least half found in the document's AP chunks now gets one question on its ICP-only lines.

## Generation (Gemini 3.8 Flash)

1. **Send up to five candidate chunks**, labelled `[Source 1: <source_type>]` to `[Source 5: ...]`. Each chunk
   already starts with its document name (PR #10).
2. **The model returns `source_index` (1-based)** for the single chunk the question comes from. Accept an
   integer or a numeric string; clamp to the range; default to the first chunk if it is missing or unreadable.
3. **Store that chunk on the banked question** (its corpus chunk id), not the other four. It is the only text
   the answer is marked against.
4. **The citation in the JSON example is rendered**, for example `"source_citation": "e.g. ACTAS CMG 14.1"`.
   The old prompt showed the model the literal text `f"e.g. {svc.short_name} CMG 14.1"` (review C-5).
5. **An unparseable generation reply is an error.** Do not bank it, do not charge for it, and retry or report.

## Marking (Gemini 3.5 Flash-Lite)

1. **Mark against the question's primary chunk only** (review H-11). Never send the other retrieved chunks:
   they let the grader credit facts from unrelated guidelines and multiply input tokens about five times.
2. **User turn format:**
   ```
   Question: <question_text>

   Source material:
   <primary chunk text>

   Student answer: <answer>
   ```
3. **A reply is valid only if it parses as a JSON object and `score` is exactly `correct`, `partial` or
   `incorrect`** (review H-5). Anything else (prose, broken JSON, a missing or unknown score, a JSON array) is a
   marking failure:
   - do not record it in mastery or history
   - refund the marking credit (or never take it)
   - tell the user the answer was not scored and let them resubmit
   - log it with the model id and `prompt_version`, so the failure rate is visible
4. **Coerce the other fields defensively:** `correct_elements` and `missing_or_wrong` become `[]` unless they
   are lists; `source_quote` and `feedback_summary` become `""` when missing.
5. **"Reveal reference" (no answer) never calls the model.** Return the primary chunk text as the quote with a
   null score, and do not charge a mark.

The desktop app returns HTTP 502 with "The marking model returned an unreadable response, so your answer was
not scored. Please try again." for case 3.

## Structured output

**Web port setting:** generation always sends the schema. Marking sends `EVALUATION_SCHEMA` only when the
`MARKING_SCHEMA` var is `on`; it ships `off`, matching the benchmarked configuration, until the benchmark is re-run
with the schema.

`complete()` in `web/src/worker/llm/gemini.ts` already accepts `responseSchema`, which sets
`responseMimeType: application/json` and `responseJsonSchema`. Use `EVALUATION_SCHEMA` from `agent.py` for
marking and a matching schema for generation. In the cloud benchmark (run without a schema), Flash-Lite
returned unparseable JSON once in 20 marks; a schema should remove that. **Re-run
`scripts/bench-cloud-models.py` with the schema on before relying on it**: on LM Studio, constrained decoding
cost gpt-oss-20b four grading points, so a schema is not free.

The benchmark in `docs/review/model-bench/` used the pre-fix generation prompt and marked against all five
chunks. Both Gemini models still marked 10/10, so the model decision stands, but token and cost figures for
marking were measured on the larger input.

## Token usage (review H-8)

Done for the web code: `complete()` returns `usage` (input, output, thinking and cached input tokens), the
gateway log id and cache status. Write these to `usage_ledger` on every generation and every mark, including
marking failures (they still cost money even though the user is refunded). The desktop app does not need
usage tracking and is unchanged.
