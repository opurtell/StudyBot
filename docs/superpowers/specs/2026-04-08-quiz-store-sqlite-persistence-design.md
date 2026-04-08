# Quiz Store SQLite Persistence

**Date:** 2026-04-08
**Status:** Approved

---

## Problem

`quiz/store.py` stores questions and sessions in module-level dicts. When the Electron app restarts the Python backend, all in-progress quiz data is lost. The frontend may still hold question/session IDs, causing 404 errors.

## Goal

Persist quiz questions and sessions to SQLite so that a brief backend restart (seconds) doesn't break the frontend. This is a "soft landing" — data is cleared on startup, not full session resumption.

## Approach

Add two tables to the existing `mastery.db`. Follow the `Tracker` class pattern (single connection, threading.Lock, _init_schema).

## Schema

```sql
CREATE TABLE IF NOT EXISTS quiz_questions (
    id TEXT PRIMARY KEY,
    question_text TEXT NOT NULL,
    question_type TEXT NOT NULL,
    source_chunks_json TEXT NOT NULL,
    source_citation TEXT NOT NULL,
    difficulty TEXT NOT NULL,
    category TEXT NOT NULL,
    primary_chunk_index INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS quiz_sessions (
    id TEXT PRIMARY KEY,
    mode TEXT NOT NULL,
    topic TEXT,
    difficulty TEXT DEFAULT 'medium',
    blacklist_json TEXT DEFAULT '[]',
    randomize INTEGER DEFAULT 1,
    asked_question_ids_json TEXT DEFAULT '[]',
    asked_chunk_contents_json TEXT DEFAULT '[]'
);
```

## Lifecycle

1. **Construction:** `QuizStore.__init__` opens the DB, runs `_init_schema()`, then deletes all rows from both tables (clears stale data from previous runs).
2. **During session:** Normal CRUD operations wrapped in `self._lock`.
3. **Restart:** On next construction, stale data is cleared again.

## Serialisation

- `Question.source_chunks` → `json.dumps([c.model_dump() for c in chunks])`
- Session lists (`blacklist`, `asked_question_ids`, `asked_chunk_contents`) → JSON text columns.
- Deserialisation constructs Pydantic models from JSON.

## File Changes

| File | Change |
|------|--------|
| `src/python/quiz/store.py` | Full rewrite: `QuizStore` class replacing module-level dicts. Public API (functions) stays identical. |
| `src/python/quiz/tracker.py` | No changes. |
| `src/python/quiz/router.py` | No changes — imports from `store.py` remain identical. |
| `src/python/quiz/models.py` | No changes. |
| `src/python/paths.py` | No changes — already has `MASTERY_DB_PATH`. |

## Singleton Management

Module creates a single `QuizStore` instance using the same DB path as `Tracker`. The `clear_all()` function is preserved for explicit mid-session resets.

## Testing

New `tests/quiz/test_store.py` following `test_tracker.py` pattern:
- tmp_path fixture for isolated DB
- CRUD operations (store/get question, store/get session, record_asked)
- Clear-on-startup verification
- Persistence across instance restarts (within the same run)
- Existing `test_router.py` unaffected — store API is unchanged.
