# Known Test Failures

**Date:** 2026-09-09 (verified on macOS arm64, Node 26.8.1, Python 3.12.14)

## Summary

| Suite | Total | Pass | Fail | Skip |
|-------|-------|------|------|------|
| Frontend (vitest) | 156 tests / 33 files | 147 | 9 | 0 |
| Python (pytest) | 784 tests | 758 | 11 | 15 |

All failures below are stale test code that has drifted behind the source it
exercises. None indicate a broken app path — the backend serves every route and
the dev app launches cleanly.

---

## Frontend Failures (9)

| Test file | Test name |
|-----------|-----------|
| `Feedback.test.tsx` | `continues quiz with ctrl+arrowright when session exists` |
| `Feedback.test.tsx` | `returns to archive with escape` |
| `Feedback.test.tsx` | `returns to quiz with ctrl+arrowright` |
| `Quiz.test.tsx` | `advances to the next question with ctrl+arrowright from inline feedback` |
| `Quiz.test.tsx` | `reveals the reference with ctrl+shift+r` |
| `Quiz.test.tsx` | `Skip button advances to the next question without exiting` |
| `Quiz.test.tsx` | `submits with ctrl+enter from outside the textarea` |
| `ServiceSetupModal.test.tsx` | `calls save on confirm with selected values` |
| `Settings.test.tsx` | `saves updated API keys and selected models` |

**Cause:** keyboard-shortcut and mock/payload expectations that no longer match
the current components. `Settings.test.tsx` asserts a request body that predates
the `active_service` field.

---

## Python Failures (11)

### 1. Google provider message shape (3)

`tests/llm/test_google_provider.py` — three tests assert `generate_content` is
called with a raw `[{"role": ..., "parts": [...]}]` dict. The provider now wraps
messages in `types.Content(...)` objects.

### 2. Provider factory (1)

`tests/llm/test_factory.py::test_create_client_unknown_provider_raises` — the
test uses `"openai"` as the unknown provider, but OpenAI is now a registered
provider, so it fails with `KeyError: 'openai'` instead of the expected
`ValueError`. Pick a genuinely unregistered name.

### 3. Ambulance Tasmania chunker (4)

`tests/python/pipeline/at/test_chunker.py` — all four fail with
`chromadb.errors.NotFoundError: Collection [guidelines_at] does not exist`. The
tests read the collection without creating it first.

### 4. CMG dose accuracy (2)

`tests/python/test_cmg_dose_accuracy.py` — `dose_lookup` is `None` in the
current structured medication data, so the tests raise `AttributeError` instead
of skipping. The skip guard checks the wrong key.

### 5. Settings router (1)

`tests/python/test_settings_router.py::test_save_settings_persists_api_keys_and_model_selection`
— the persisted file now also carries `active_service`, which the equality
assertion does not expect.

---

## Notes

- `pyproject.toml` sets `testpaths = ["tests"]`. Without it pytest walks into
  `release/` and collects the vendored third-party tests inside a previously
  built `.app`, producing ~85 spurious collection errors.
- `tests/renderer/setup.ts` shims `window.localStorage`. Node 26 defines its own
  non-configurable `localStorage` global, which prevents vitest's jsdom
  environment from attaching jsdom's implementation; without the shim all 156
  frontend tests fail in `beforeEach`.
