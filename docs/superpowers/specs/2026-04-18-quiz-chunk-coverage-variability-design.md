---
title: Quiz Chunk Coverage & Variability
date: 2026-04-18
status: approved
---

# Quiz Chunk Coverage & Variability

## Problem

Two related issues reduce quiz quality over time:

1. **Semantic bias** — retrieval is purely cosine-similarity driven. Chunks peripheral to common query terms (rare presentations, edge-case protocols) are structurally unreachable and never surface.
2. **Dedup fragility** — the existing `used_chunks` binary exclusion list (max 300 entries) is cleared by `clear_mastery_data()` during testing and doesn't scale to large corpora. The 300-entry cap means the window shrinks quickly in real use.

The result: some topic areas never appear; others resurface repeatedly within a short time.

---

## Goals

- All chunks in the corpus have a realistic chance of appearing over time.
- Within a category/topic, questions vary across the full range of that category's content — not just top cosine-similarity matches.
- Random mode injects genuinely random corpus samples to reach peripheral chunks.
- Category/topic/guideline modes use coverage-weighted scoring for intra-category variety without straying outside the selected scope.
- The mechanism is robust across test resets: clearing mastery clears coverage too (intentional — the behaviour is consistent by design).

---

## Non-Goals

- Guaranteeing a specific number of questions before any chunk repeats (a strict "no-repeat" SRS is out of scope).
- Surfacing low-quality or very short chunks — the LLM already filters based on source material quality.
- Changes to the evaluation path (`evaluate_answer`).

---

## Architecture

### 1. Coverage Table (`tracker.py`)

Replace the `used_chunks` table with `chunk_coverage`:

```sql
CREATE TABLE IF NOT EXISTS chunk_coverage (
    content_key TEXT PRIMARY KEY,   -- first 200 chars of chunk content
    use_count   INTEGER NOT NULL DEFAULT 1,
    last_used   TEXT NOT NULL       -- ISO datetime('now')
);
CREATE INDEX IF NOT EXISTS idx_coverage_last_used ON chunk_coverage(last_used);
```

**Migration:** On schema init, check if `used_chunks` exists using `sqlite_master`. If it does, copy its rows into `chunk_coverage` (use_count=1, last_used=datetime('now')) then drop `used_chunks`. The check-and-migrate is done inline in `_init_schema()` — no separate migration table needed, because the guard is the `used_chunks` table's existence itself (once dropped, the migration never re-runs).

**Tracker API changes:**

| Method | Change |
|--------|--------|
| `record_used_chunks(keys)` | Upsert into `chunk_coverage`: `INSERT OR REPLACE` incrementing `use_count`, setting `last_used=datetime('now')`. No size cap. |
| `get_chunk_scores(keys: set[str]) -> dict[str, float]` | New. Returns coverage weight for each key in `keys`. Keys absent from the table get weight 1.0. See formula below. |
| `get_recent_chunk_keys(limit)` | **Behaviour change:** now returns keys where `last_used` is within the last 7 days (previously returned the 300 most recent regardless of age). This intentionally narrows the hard-exclusion window; coverage-weighted scoring handles older chunks softly. |
| `clear_mastery_data()` | Also truncates `chunk_coverage` (existing behaviour extended). |

**Coverage weight formula:**

```python
days_since = (datetime.utcnow() - datetime.fromisoformat(last_used)).days
recency_factor = min(1.0, days_since / 7.0)   # 0.0 on day 0, 1.0 on day 7+
weight = (1.0 / (use_count + 1)) + recency_factor * (1.0 - 1.0 / (use_count + 1))
       # = lerp(1/(use_count+1), 1.0, recency_factor)
```

- Unseen chunks: weight = 1.0.
- Used once today: weight ≈ 0.5.
- Used 3 times today: weight ≈ 0.25.
- After 7 days: weight returns to 1.0 regardless of use_count.

The full reset after 7 days is intentional: this app has a small corpus relative to a spaced-repetition system, and the goal is thorough rotation over days/weeks, not permanent prioritisation of rarely-seen chunks. An implementer should note this is an explicit design choice.

All weights are bounded [0.0, 1.0].

---

### 2. `content_key` on `RetrievedChunk` (`models.py`)

Add a computed property to `RetrievedChunk`:

```python
@property
def content_key(self) -> str:
    return self.content[:200]
```

This eliminates repeated slicing at call sites and makes the key derivation canonical. All existing `c.content[:200]` usages in `tracker.py` and `router.py` should be updated to `c.content_key`.

---

### 3. Coverage-Weighted Retrieval (`retriever.py`)

`retrieve()` gains an optional `tracker` parameter:

```python
def retrieve(
    self,
    query: str,
    n: int = 5,
    filters: dict | None = None,
    exclude_categories: list[str] | None = None,
    skill_level: str = "AP",
    exclude_content_keys: set[str] | None = None,
    source_restriction: str | None = None,   # existing param — preserved unchanged
    tracker=None,                            # Tracker | None — new param
) -> list[RetrievedChunk]:
```

`source_restriction` is an existing parameter (`None` = all sources, `"cmg"` = CMG collection only) — it must be preserved in the updated signature. It is not changed by this work.

If `tracker is None`, the method falls back to the existing shuffle-and-slice behaviour (backwards compat for tests).

**New scoring step** (inserted after exclusion filtering, replacing `random.shuffle`). Use local tuples to avoid mutating `RetrievedChunk` instances (which are Pydantic models that reject arbitrary attribute assignment):

```python
if tracker is not None:
    candidate_keys = {c.content_key for c in all_chunks}
    scores = tracker.get_chunk_scores(candidate_keys)
    scored = [
        (
            chunk.relevance_score
            + random.uniform(0, 0.05) * scores.get(chunk.content_key, 1.0),
            chunk,
        )
        for chunk in all_chunks
    ]
    scored.sort(key=lambda t: t[0], reverse=True)
    all_chunks = [chunk for _, chunk in scored]
else:
    random.shuffle(all_chunks)
return all_chunks[:n]
```

**All** `retrieve()` calls inside `generate_question()` in `agent.py` **must** pass `tracker=tracker` — including the fallback call that retries without chunk exclusions (currently lines ~120–128 in the live code). This is the primary wiring point.

**Scoring magnitude note:** `relevance_score` is stored as `-distance` (typically in [-1, 0] for cosine). The coverage bonus is at most `0.05 × 1.0 = 0.05`. This is intentionally small: the bonus is designed to break ties and re-rank within clusters of similarly-scoring chunks, not to pull semantically distant chunks above close matches. A chunk that is genuinely far from the query will not be promoted over a close match purely on coverage grounds.

---

### 4. `get_random_chunk()` on `Retriever` (`retriever.py`)

Add a public method to encapsulate random corpus sampling, so `agent.py` never touches private collection attributes:

```python
def get_random_chunk(
    self,
    exclude_content_keys: set[str] | None = None,
    skill_level: str = "AP",
) -> RetrievedChunk | None:
    """Return a single uniformly random chunk from the combined corpus."""
    collections = [self._notes, self._cmgs]
    random.shuffle(collections)  # randomise which collection is tried first
    for col in collections:
        try:
            total = col.count()
            if total == 0:
                continue
            # Fetch all IDs, pick one at random, retrieve by ID
            all_ids = col.get(include=[])["ids"]
            if not all_ids:
                continue
            chosen_id = random.choice(all_ids)
            result = col.get(ids=[chosen_id], include=["documents", "metadatas"])
            chunks = self._parse_results(
                {"documents": [result["documents"]],
                 "metadatas": [result["metadatas"]],
                 "distances": [[0.0]]},
                col.name,
            )
            if not chunks:
                continue
            chunk = chunks[0]
            if exclude_content_keys and chunk.content_key in exclude_content_keys:
                continue  # skip and try next collection (one attempt per collection)
            return chunk
        except Exception:
            continue
    return None  # corpus empty or all candidates excluded

```

**Accepted limitation:** exclusion checking retries once per collection (not within a collection). If both collections return excluded chunks, the method returns `None` and the caller falls back to the normal semantic path. This is acceptable given the corpus size — in practice the probability of all chunks in both collections being in `exclude_content_keys` is negligible. A full per-collection retry loop is out of scope.

Note: `col.name` is used to identify the collection (ChromaDB collections have a `.name` attribute). The `_parse_results` call already handles both `"notes"` and `"cmgs"` collection names — no change needed there.

---

### 5. Random Injection (`agent.py`)

Module-level constant:

```python
RANDOM_INJECTION_PROBABILITY = 0.25
```

Only active when `mode == "random"`. Injection branch in `generate_question()`:

```python
injected_chunk = None
if mode == "random" and random.random() < RANDOM_INJECTION_PROBABILITY:
    injected_chunk = retriever.get_random_chunk(
        exclude_content_keys=exclude_keys or None,
        skill_level=skill_level,
    )
    # get_random_chunk returns None if corpus is empty or retry exhausted —
    # fall back to normal path silently in that case

if injected_chunk is not None:
    # Fetch 4 semantic chunks to accompany the injected one
    semantic_chunks = retriever.retrieve(
        query=query, n=4, filters=filters,
        exclude_categories=blacklist, skill_level=skill_level,
        exclude_content_keys=exclude_keys or None, tracker=tracker,
    )
    chunks = [injected_chunk] + semantic_chunks
else:
    chunks = retriever.retrieve(
        query=query, n=n_to_fetch, filters=filters,
        exclude_categories=blacklist, skill_level=skill_level,
        exclude_content_keys=exclude_keys or None, tracker=tracker,
    )
    if randomize and len(chunks) > 5:
        chunks = random.sample(chunks, 5)
    else:
        chunks = chunks[:5]
```

If `get_random_chunk()` returns `None` (empty corpus, or all candidates excluded after one retry), the question is generated using the normal semantic path with 5 chunks — no error raised.

All other modes (`topic`, `gap_driven`, `clinical_guidelines`, `guideline_id`) always take the normal semantic path.

---

### 6. Integration Points

| File | Change |
|------|--------|
| `tracker.py` | Replace `used_chunks` with `chunk_coverage`; add index; migrate existing rows; add `get_chunk_scores()`; update `record_used_chunks()`, `get_recent_chunk_keys()`, `clear_mastery_data()` |
| `models.py` | Add `content_key` property to `RetrievedChunk` |
| `retriever.py` | Add `tracker` param to `retrieve()` (preserving existing `source_restriction` and all other params); add coverage-weighted scoring step; add `get_random_chunk()` method |
| `agent.py` | Add random injection branch for `mode == "random"`; pass `tracker=tracker` to all `retriever.retrieve()` calls |
| `router.py` | Update `c.content[:200]` → `c.content_key` (cosmetic); no structural changes — `record_used_chunks()` call at line 156 is already correct after the method is updated |

No changes to `store.py` or any frontend code.

---

## Testing

Existing tests pass because `tracker=None` preserves the old shuffle-and-slice behaviour in `retrieve()`.

New tests:

| Test | Assertion |
|------|-----------|
| `tracker.get_chunk_scores()` — unseen key | Returns 1.0 |
| `tracker.get_chunk_scores()` — used once today | Returns ~0.5 (within ±0.05) |
| `tracker.get_chunk_scores()` — used 3× today | Returns ~0.25 (within ±0.1) |
| `tracker.get_chunk_scores()` — used, 7+ days ago | Returns 1.0 |
| Coverage-weighted retrieval | With mock tracker returning low weight for top-similarity chunk, that chunk drops below a lower-similarity but unseen chunk |
| `get_random_chunk()` — normal | Returns a valid `RetrievedChunk` |
| `get_random_chunk()` — empty corpus | Returns `None` without raising |
| `get_random_chunk()` — excluded chunk | Skips to next collection; returns different chunk |
| Random injection fires in random mode | Across 200 calls, injection rate is within 0.15–0.35 (±10% of 0.25 at 95% confidence) |
| Random injection suppressed in topic mode | Across 50 calls with `mode="topic"`, injection never fires |
| Migration | If `used_chunks` table exists pre-migration, rows appear in `chunk_coverage` with `use_count=1`; `used_chunks` is dropped |

---

## Migration & Rollout

- Schema migration runs automatically in `_init_schema()` — no manual step needed.
- First launch after deploy: existing dedup history is preserved (migrated with `use_count=1`).
- `used_chunks` table is dropped after migration; the absence of the table is the idempotency guard.
