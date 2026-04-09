# Standalone Packaging Playbook — macOS and Windows

**Last Updated:** 2026-04-06

## Purpose

This is the living source of truth for turning this project into standalone desktop applications for macOS and Windows.

Use it to:

- plan and track the packaging work
- record decisions and why they were made
- capture mistakes, dead ends, and platform-specific learnings
- rebuild a new release quickly after major product changes

This document starts from the dated implementation plan at `docs/superpowers/plans/2026-04-04-standalone-packaging-macos-windows.md` and now supersedes it as the ongoing operational guide. Keep the dated plan as a historical snapshot; update this playbook as packaging work progresses.

## Maintenance Rules

- Update this file whenever packaging architecture, release steps, signing approach, runtime paths, bundled assets, or platform constraints change.
- Update this file whenever a build fails for a reason that future work should avoid.
- Update this file whenever a new manual workaround is discovered, removed, or replaced.
- Do not close packaging work without updating the status tracker, decision log, and rebuild checklist sections below.

## Current Status

Legend: `[ ]` not started | `[~]` in progress | `[x]` complete | `[!]` blocked

**Release objective:** installable standalone apps for macOS and Windows that do not require a pre-installed Python and that start the bundled FastAPI backend automatically.

**Current packaging maturity:** Phases A-E and P complete. Verification (Phase F) partially complete — automated validation scripts and tests pass. CI/release automation (Phase H) complete. Signing (Phase G) partially complete — macOS ad-hoc signing with hardenedRuntime and entitlements configured; paid certificate signing and notarisation deferred.

## Decision Summary

These decisions are fixed unless explicitly revisited and the change is logged in the decision log.

### Packaging model

- Product shape: packaged Electron desktop apps, not a web deployment.
- Backend packaging approach: embedded CPython plus installed wheel tree.
- Backend form: regular Python files plus installed packages, not a single frozen executable.
- Deferred backend alternatives: PyInstaller and Nuitka.

### Release 1 scope

- Installable app for macOS and Windows.
- Bundled Python runtime and backend dependencies.
- Bundled renderer build.
- Bundled read-only seed data required for first launch.
- Writable user state stored under the OS user-data directory.
- Unsigned internal test builds are acceptable during implementation; signing comes after clean-machine runtime validation.

### Release 1 non-goals

- Web deployment.
- Hosted backend architecture.
- PyInstaller or Nuitka packaging.
- Universal builds for every architecture.
- Bundling Playwright browser binaries in the default package.
- Auto-update infrastructure.

## Release Definition

The standalone release is complete when a user on a clean machine can:

- install the app without separately installing Python
- launch the app and have the backend start automatically
- open quiz, guidelines, settings, and search successfully on first run
- persist settings and study data across restarts
- use the app without runtime writes to the installation directory

Pipeline and browser-refresh support are outside the base standalone release unless added later and documented here.

## Target Matrix

| Platform | Architecture | Output | Release 1 | Notes |
|----------|--------------|--------|-----------|-------|
| macOS | `arm64` | `.dmg` | In scope | Apple Silicon Mac build |
| macOS | `x64` | `.dmg` | In scope | Intel Mac build |
| Windows | `x64` | `nsis` installer | In scope | Primary Windows target |
| macOS | universal | Deferred | Out of scope | Revisit after Release 1 if dual-build maintenance becomes too costly |
| Windows | `arm64` | Deferred | Out of scope | Revisit after Release 1 |
| Windows | portable build | Deferred | Out of scope | Revisit after Release 1 |

## Product Scope Decisions

### Bundled data

- Ship read-only source data required by the app under the packaged app root.
- Store user-writable runtime data under the OS user-data directory.
- Copy or initialise writable files on first launch only when required.

### Pipeline features

- The base standalone package does not include Playwright browser binaries.
- Pipeline features that need browser binaries should be gated behind an explicit later download path.
- Standalone packaging must not block on pipeline-browser support.

### Runtime configuration

- `config/settings.json` becomes user-data owned at runtime.
- `config/settings.example.json` remains the bundled read-only default.
- Runtime API keys remain user-provided.
- Packaged apps must not depend on a repo-root `.env` file on end-user machines.

## Architecture Contract

### Packaged layout

The packaged app should resolve to a layout conceptually equivalent to:

```text
resources/
  app.asar
  backend/
    bin/python
    python.exe
    Lib/ or lib/
    site-packages/ or equivalent installed tree
    app/
      src/python/...
  app-root/
    config/settings.example.json
    data/cmgs/...
    data/chroma_db/...
    data/... other bundled read-only runtime seeds
```

Exact folder names can change, but these runtime guarantees cannot:

- Electron can spawn a real Python executable from disk.
- Python can import from the bundled backend tree.
- Python can find read-only bundled assets.
- Python can find writable user-data paths independent of install location.

### Runtime environment contract

Electron must pass these environment variables to the backend:

- `STUDYBOT_USER_DATA`
- `STUDYBOT_APP_ROOT`
- `STUDYBOT_HOST`
- `STUDYBOT_PORT`
- `PYTHONPATH` as required by the packaged backend layout

### Writable versus read-only paths

**Read-only bundled assets**

- packaged source defaults
- packaged CMG and reference data
- packaged backend code and dependencies

**Writable user-data assets**

- `settings.json`
- ChromaDB persistence
- SQLite mastery database
- logs
- any future downloaded browser or pipeline components

No runtime writes should target the install directory.

## Canonical Files

| Path | Responsibility |
|------|----------------|
| `Guides/standalone-packaging-macos-windows.md` | Living packaging playbook, decisions, rebuild instructions |
| `docs/superpowers/plans/2026-04-04-standalone-packaging-macos-windows.md` | Historical snapshot of the original standalone packaging plan |
| `src/python/paths.py` | Central runtime path resolution |
| `src/python/main.py` | Backend entrypoint and bind configuration |
| `src/python/settings/router.py` | Settings file resolution |
| `src/python/llm/factory.py` | Runtime config lookup |
| `src/python/llm/models.py` | Runtime model discovery |
| `src/python/pipeline/run.py` | Pipeline runtime path handling |
| `src/python/pipeline/personal_docs/run.py` | Personal docs runtime path handling |
| `src/electron/main.js` | Backend process spawn and packaged runtime setup |
| `package.json` or `electron-builder.yml` | Builder targets, resources, output configuration |
| `scripts/package-backend.sh` | macOS backend payload build script (downloads standalone CPython) installs deps from `pyproject.toml`) |
| `scripts/package-backend.ps1` | Windows backend payload build script (downloads standalone CPython, installs deps from `pyproject.toml`) |
| `scripts/verify-backend-payload.sh` | macOS automated verification of staged backend payload |
| `scripts/verify-backend-payload.ps1` | Windows automated verification of staged backend payload |
| `.github/workflows/release-build.yml` | Packaging CI and artifact workflow |
| `.github/workflows/personal-build.yml` | Personal build workflow (all data sources) |
| `scripts/upload-personal-data.sh` | Uploads archive chroma_db to GitHub Release for personal builds |
| `tests/python/test_paths_packaging.py` | Packaging path resolution tests |

## Future Rebuild Workflow

When major repo changes land and a new app build is needed, use this sequence:

1. Read this playbook first, especially the decision log, current known issues, and rebuild checklist.
2. Confirm whether any changed code affects runtime paths, packaged assets, first-run seeding, Electron backend startup, or signing.
3. Update the impacted sections of this playbook before or during implementation, not after memory has faded.
4. Rebuild the backend payload for each target platform.
5. Build Electron artifacts for each target platform.
6. Run the verification matrix and log outcomes in this document.
7. Record any new failure mode, workaround, or decision before considering the release done.

## Execution Plan and Tracker

### Phase A: Path and configuration model

**Objective:** make backend code independent of repo-root assumptions.

**Files**

- Modify: `src/python/paths.py`
- Modify: `src/python/settings/router.py`
- Modify: `src/python/llm/factory.py`
- Modify: `src/python/llm/models.py`
- Create: `tests/python/test_paths_packaging.py`

- [x] Step A1: Extend `paths.py` to compute `APP_ROOT`, `USER_DATA_DIR`, `DATA_DIR`, `CONFIG_DIR`, `CHROMA_DB_DIR`, `MASTERY_DB_PATH`, and related writable paths from packaging-safe inputs.
- [x] Step A2: Remove duplicate project-root discovery from settings and LLM modules so all runtime path resolution flows through `paths.py`.
- [x] Step A3: Make packaged runtime configuration depend on bundled defaults plus user-data overrides, not repo-local `.env` assumptions.
- [x] Step A4: Add tests using `STUDYBOT_USER_DATA=<tmp_path>` and assert all writable paths stay under user data.
- [x] Step A5: Run `PYTHONPATH=src/python python3 -m pytest tests/python/test_paths_packaging.py -v`.
- [x] Step A6: Run `PYTHONPATH=src/python python3 -m pytest tests/ -v` and fix regressions.

### Phase B: Electron main process

**Objective:** make production Electron spawn the bundled backend instead of `python3` on PATH.

**Files**

- Modify: `src/electron/main.js`

- [x] Step B1: Introduce a helper such as `getBackendCommand()` returning `{ executable, args, cwd, env }`.
- [x] Step B2: Keep development mode on `python3` with the repo backend entrypoint.
- [x] Step B3: Make production mode use the bundled runtime executable and packaged backend entrypoint.
- [x] Step B4: Pass `STUDYBOT_USER_DATA`, `STUDYBOT_APP_ROOT`, `STUDYBOT_HOST`, `STUDYBOT_PORT`, and packaged `PYTHONPATH`.
- [x] Step B5: Ensure Windows absolute paths and spaces work without requiring a shell.
- [x] Step B6: Smoke test with a staged backend payload so `NODE_ENV=production electron .` reaches `/health`.

### Phase C: Backend payload build scripts

**Objective:** produce repeatable platform-specific backend payloads for Electron Builder.

**Files**

- Create: `scripts/package-backend.sh`
- Create: `scripts/package-backend.ps1`
- Create or modify: Python dependency lockfile inputs

- [x] Step C1: Choose and commit a deterministic lockfile strategy for bundled Python dependencies.
- [x] Step C2: macOS script accepts a target architecture input of `arm64` or `x64`.
- [x] Step C3: macOS script downloads the matching embedded Python, stages dependencies, copies backend code, and emits an architecture-specific payload under `build/resources/backend-mac-<arch>`.
- [x] Step C4: Windows script downloads embedded Python for `x64`, stages dependencies, copies backend code, and emits `build/resources/backend-win-x64`.
- [x] Step C5: Validate staged runtimes by importing required modules such as `fastapi`, `uvicorn`, and `chromadb` for each emitted payload.

### Phase D: First-run seeding and runtime data

**Objective:** ensure first launch creates only the writable files it needs under user data.

- [x] Step D1: Choose one owner for first-run seeding logic, Electron or Python.
- [x] Step D2: On first launch, create `config/settings.json` under user data from bundled `config/settings.example.json` if missing.
- [x] Step D3: Seed required writable runtime directories under user data.
- [x] Step D4: Keep bundled CMG and reference assets read-only unless runtime mutation requires copying.
- [x] Step D5: Document exactly which datasets are bundled read-only versus initialised writable.

### Phase E: Electron Builder configuration

**Objective:** build installable artifacts that include the staged backend payload and bundled runtime assets.

- [x] Step E1: Add `extraResources` for the staged backend payload.
- [x] Step E2: Add bundled read-only app assets required at runtime.
- [x] Step E3: Set `directories.output` to `release/`.
- [x] Step E4: Configure separate macOS `dmg` targets for `arm64` and `x64`. Arch list removed from `electron-builder.yml`; CLI flag (`--arm64`/`--x64`) controls which single arch is built.
- [x] Step E5: Ensure each macOS artifact includes only the matching architecture-specific backend payload. Fixed by removing the yml arch list so only one DMG is produced per build, paired with the staged payload for that arch.
- [x] Step E6: Configure Windows `nsis` target for `x64`.
- [x] Step E7: Keep the Python runtime payload outside `app.asar`.
- [x] Step E8: Run `npm run build` for each supported architecture after staging and confirm expected artifacts under `release/`.

### Phase P: Prerequisite Fixes

**Objective:** resolve gaps in Phases A-E that would prevent packaged apps from running on clean machines.

- [x] Step P1: Packaging scripts now install dependencies directly from `pyproject.toml` using `pip install --target` instead of requiring a separate `requirements.txt`.
- [x] Step P2: Packaging scripts output to `build/resources/backend/` (matching `electron-builder.yml` expectations) instead of arch-specific directory names.
- [x] Step P3: Packaging scripts download standalone CPython from python-build-standalone releases instead of creating venvs from the host Python. Tag `20260325`, Python `3.12.13`.
- [x] Step P4: `PYTHONHOME` added to the Electron production env so standalone Python can find its stdlib. `PYTHONPATH` now includes both `lib` (installed packages) and backend source.
- [x] Step P5: All backend routers now resolve data paths through `paths.py` constants instead of bare relative paths. Added `CMG_STRUCTURED_DIR`, `REFDOCS_DIR`, `CPDDOCS_DIR`, `NOTABILITY_NOTE_DOCS_DIR`, `PERSONAL_STRUCTURED_DIR`, `RAW_NOTES_DIR`, `CLEANED_NOTES_DIR` to `paths.py`.
- [x] Step P6: `electron-builder.yml` updated to bundle `data/cmgs/structured/` as read-only assets for first-launch guidelines and medication data.
- [x] Step P7: Build orchestration npm scripts added: `build:mac-arm64`, `build:mac-x64`, `build:win-x64`, `build:backend-mac-arm64`, `build:backend-mac-x64`, `build:backend-win`.

### Phase F: Verification

**Objective:** prove packaged apps work on clean machines before signing and CI work.

- [x] Step F1: Add a minimal automated check that the staged backend layout exists and imports required modules.
- [x] Step F2: Keep Python and renderer tests green after packaging changes.
- [ ] Step F3: Validate the `arm64` build on a clean Apple Silicon macOS machine with no system Python requirement.
- [ ] Step F4: Validate the `x64` build on a clean Intel macOS machine with no system Python requirement.
- [ ] Step F5: Validate on a clean Windows machine with no system Python requirement.

### Phase G: Signing and notarisation

**Objective:** move from working installers to publicly distributable installers.

- [x] Step G1 (macOS): Ad-hoc signing with hardenedRuntime and entitlements configured. `identity: "-"` in `electron-builder.yml` triggers ad-hoc codesign without a paid Apple Developer certificate. Entitlements in `build/entitlements.mac.plist` allow V8 JIT, unsigned executable memory, and library validation bypass (needed for bundled Python dylibs). Gatekeeper will still show a bypassable warning until a Developer ID certificate and notarisation are configured.
- [ ] Step G1 (macOS, paid): Apple Developer Program enrolment, Developer ID Application certificate, notarisation secrets, and Gatekeeper validation. **Deferred** — requires paid certificate ($99/year Apple Developer Program).
- [ ] Step G2 (Windows): Authenticode certificate and signed installer validation. **Deferred** — requires paid Authenticode certificate. Self-signed certs can be created for free but do not suppress SmartScreen warnings. electron-builder is configured with `signingHashAlgorithms: ['sha256']` so signing works when `CSC_LINK` and `CSC_KEY_PASSWORD` env vars are set.

### Phase H: CI and release automation

**Objective:** make packaging reproducible once local packaged runtime behaviour is proven.

- [x] Step H1: Create `.github/workflows/release-build.yml` triggered on `workflow_dispatch` and `v*` tags.
- [x] Step H2: Build matrix for `macos-latest` (arm64), `macos-13` (x64), and `windows-latest` (x64).
- [x] Step H3: Each job checks out repo, runs the backend packaging script, verifies the payload, builds the Electron artifact, and uploads to GitHub Actions artifacts.
- [x] Step H4: Draft release created via `softprops/action-gh-release@v2` after all builds succeed. Manual publish step.

## Acceptance Criteria

- [ ] macOS installer builds successfully for `arm64`
- [ ] macOS installer builds successfully for `x64`
- [ ] Windows installer builds successfully for `x64`
- [ ] Neither packaged app requires a system Python installation
- [ ] Backend starts automatically on first launch and `/health` succeeds
- [ ] Quiz, guidelines, settings, and search load successfully on first run
- [ ] Settings persist across restart
- [ ] Writable runtime files are created under the OS user-data directory, not inside the install directory
- [ ] Clean-machine validation has been completed on Apple Silicon macOS, Intel macOS, and Windows

## Verification Matrix

| Check | macOS | Windows | Notes |
|-------|-------|---------|-------|
| Install from artifact | Pending | Pending | |
| No system Python installed | Pending | Pending | |
| App launches and backend `/health` is OK | Pending | Pending | |
| Quiz page loads | Pending | Pending | |
| Guidelines page loads | Pending | Pending | |
| Search works with bundled data | Pending | Pending | |
| Settings persist across restart | Pending | Pending | |
| Chroma, DB, and config live under user data | Pending | Pending | |
| Install directory remains read-only at runtime | Pending | Pending | |
| Uninstall behaviour and retained user-data policy documented | Pending | Pending | |

## Decision Log

| Date | Decision | Why | Status |
|------|----------|-----|--------|
| 2026-04-04 | Use Electron packaged desktop apps rather than a web deployment | The current product architecture already depends on a local Electron shell and local FastAPI backend | Active |
| 2026-04-04 | Use embedded CPython plus installed wheel tree instead of a frozen backend binary | Lower implementation risk and preserves normal Python runtime behaviour for backend code and native dependencies | Active |
| 2026-04-04 | Keep backend on `127.0.0.1:7777` in packaged builds | Aligns with the current app architecture and avoids unnecessary backend redesign during Release 1 | Active |
| 2026-04-04 | Keep Python runtime and backend import tree outside `app.asar` | Python cannot execute from inside `app.asar` | Active |
| 2026-04-04 | Store writable runtime state under the OS user-data directory | Prevents writes into the install directory and supports normal desktop app behaviour | Active |
| 2026-04-04 | Exclude Playwright browser binaries from the base standalone package | Keeps base release smaller and avoids blocking packaging on browser-dependent pipeline features | Active |
| 2026-04-05 | Promote this playbook to the living packaging source of truth | The dated plan is useful as a snapshot, but future rebuilds need tracked decisions, verification history, and repeatable release instructions in one place | Active |
| 2026-04-05 | Ship separate macOS `arm64` and `x64` installers instead of a universal Mac build | The bundled Python runtime and native dependencies make dual per-arch packaging simpler and lower risk than a universal macOS app | Active |
| 2026-04-06 | Defer Apple Developer Program signing and notarisation (Step G1) | Unsigned builds are functional; Gatekeeper shows a bypassable warning; certificates only suppress that warning | Active |
| 2026-04-06 | Download standalone CPython from python-build-standalone instead of host venv | Host venv binary depends on host shared libraries; standalone distributions are self-contained and relocatable | Active |
| 2026-04-06 | Install deps from `pyproject.toml` directly with `pip install --target` instead of `requirements.txt` | Avoids lockfile maintenance; `pyproject.toml` is already the dependency source of truth | Active |
| 2026-04-06 | Output payload to `build/resources/backend/` (flat) matching electron-builder expectations | Arch-specific naming was unnecessary since only one payload is staged per build invocation | Active |
| 2026-04-06 | Add `PYTHONHOME` env var in Electron production spawn so standalone Python finds its stdlib | python-build-standalone sets `sys.prefix` at build time; `PYTHONHOME` overrides it at runtime | Active |
| 2026-04-06 | Bundle CMG structured JSON as read-only assets; defer ChromaDB pre-population | Guidelines and medication endpoints need data at first launch; ChromaDB for quiz/search requires user pipeline run | Superseded — ChromaDB now pre-built and bundled |
| 2026-04-07 | Pre-build ChromaDB index during packaging; copy to user data on first launch | Eliminates first-launch embedding delay and removes dependency on embedding model availability at startup. Bundled DB is copied from read-only app root to writable user data. Auto-seed falls back to chunker if no bundled DB exists (dev environments). Per-source clear endpoints let users selectively remove indexed data. | Active |
| 2026-04-06 | Remove `arch` list from `electron-builder.yml` mac and win targets | The `--x64`/`--arm64` CLI flag does not override the yml arch list, so both arches were built on every run; each arch DMG bundled the same payload from the single flat `build/resources/backend/` directory | Active |
| 2026-04-07 | Add personal build workflow that bundles all data sources | The standard release only bundles CMG data. The personal build includes notability notes, REFdocs, and CPDdocs by uploading the archive's pre-built ChromaDB to a GitHub Release and downloading it in CI. `PERSONAL_BUILD=1` env var opts out of the CMG-only ChromaDB pre-build step. | Active |
| 2026-04-06 | Build per-arch Mac DMGs sequentially, never in parallel | The backend payload directory is overwritten per build; sequential builds with rename between them ensures each DMG contains the correct arch-specific binaries | Active |
| 2026-04-08 | Ad-hoc macOS signing with hardenedRuntime and entitlements | Free alternative to paid Apple Developer signing. `identity: "-"` triggers `codesign --sign -` without a certificate. Entitlements (`allow-jit`, `allow-unsigned-executable-memory`, `disable-library-validation`) are required for Electron + bundled Python under hardenedRuntime. Gatekeeper still warns but the warning is bypassable. | Active |
| 2026-04-08 | Configure Windows `signingHashAlgorithms` for future Authenticode signing | electron-builder is ready to sign Windows builds when `CSC_LINK`/`CSC_KEY_PASSWORD` env vars are provided. No cert is bundled; unsigned builds work as before. | Active |
| 2026-04-08 | Set window title from `extraMetadata.displayName` injected into built package.json | `productName` controls the macOS bundle name and Windows executable name correctly, but the HTML `<title>` (which drives the window title bar and taskbar) was still "Clinical Recall Assistant". Each electron-builder config now injects a `displayName` field into the built app's `package.json` via `extraMetadata`. `main.js` reads this at startup and sets the BrowserWindow `title`, then blocks `page-title-updated` to prevent the renderer from overriding it. | Active |

## Personal Build Workflow

The personal build produces a desktop app that includes all data sources in the bundled ChromaDB — CMGs, notability notes, REFdocs, and CPDdocs — instead of CMG-only data.

### How it works

1. The pre-built ChromaDB from `../StudyBot-archive/data/chroma_db/` is uploaded to a GitHub Release tagged `personal-data` via `scripts/upload-personal-data.sh`.
2. The `.github/workflows/personal-build.yml` workflow (manual trigger only) downloads the tarball, extracts it, and bundles it with the app.
3. The `PERSONAL_BUILD=1` env var tells `package-backend.sh`/`.ps1` to skip the CMG-only ChromaDB pre-build and use the pre-extracted index instead.

### Refreshing the personal data

After updating notes or other data in the archive:

```bash
# 1. Rebuild the ChromaDB locally if needed
# 2. Re-upload to GitHub
bash scripts/upload-personal-data.sh

# 3. Trigger a new personal build
gh workflow run personal-build.yml
```

### Key files

| Path | Responsibility |
|------|----------------|
| `scripts/upload-personal-data.sh` | Uploads archive chroma_db to GitHub Release |
| `.github/workflows/personal-build.yml` | CI workflow: download data, build, draft release |
| `scripts/package-backend.sh` | Skips ChromaDB pre-build when `PERSONAL_BUILD=1` |
| `scripts/package-backend.ps1` | Windows equivalent of the above |

## Known Risks and Deferred Work

- Playwright browser bundling remains deferred.
- Pipeline refresh support in the default standalone package remains deferred.
- macOS universal builds remain deferred in favour of separate `arm64` and `x64` Mac installers.
- Windows portable builds remain deferred.
- PyInstaller and Nuitka remain deferred.
- Auto-update infrastructure remains deferred.
- Apple Developer Program signing and notarisation (Step G1, paid) remains deferred. Ad-hoc signing is configured as a free alternative.

## Known Unknowns

- Exact Python lockfile format for deterministic cross-platform backend staging. → Resolved: install directly from `pyproject.toml` with `pip install --target`.
- Whether first-run seeding is cleaner in Electron or Python for this repo. → Resolved: Python (`seed.py`).
- Final signed-distribution requirements and secrets handling for Apple and Windows.
- The exact minimal read-only asset set required for first-launch guidelines and medication data. → Resolved: `data/cmgs/structured/*.json` bundled via `electron-builder.yml extraResources`. ChromaDB now also pre-built and bundled at `build/resources/data/chroma_db/`.
- macOS x64 build on arm64 runner: → Resolved: `macos-13` (Intel) GitHub Actions runner used for `release-build.yml`.

## Build Notes and Learnings

Add dated entries here as packaging work progresses. Record failures as well as wins.

### 2026-04-05

- Created this living playbook from the original standalone packaging plan.
- No implementation outcomes recorded yet.

### 2026-04-06 — Phases P, F1-F2, H implementation

- Phase P1-P4 (backend packaging rewrite): `scripts/package-backend.sh` and `scripts/package-backend.ps1` now download standalone CPython from python-build-standalone (tag `20260325`, Python 3.12.13) instead of creating venvs from host Python. Output goes to `build/resources/backend/` (matching `electron-builder.yml`). Dependencies installed directly from `pyproject.toml` via `pip install --target`. `PYTHONHOME` added to Electron production env so standalone Python finds its stdlib. `PYTHONPATH` now includes `lib/` (installed packages) and backend source.
- Phase P5 (router path fixes): `guidelines/router.py`, `medication/router.py`, and `sources/router.py` now resolve data paths through `paths.py` constants (`CMG_STRUCTURED_DIR`, `REFDOCS_DIR`, `CPDDOCS_DIR`, etc.) instead of bare relative `Path("data/cmgs/...")` calls. Added 8 new path constants to `paths.py`.
- Phase P6 (CMG data bundling): `electron-builder.yml` updated to bundle `data/cmgs/structured/` as read-only assets. ChromaDB pre-population deferred — quiz/search requires user pipeline run.
- Phase P7 (build scripts): Added npm scripts: `build:mac-arm64`, `build:mac-x64`, `build:win-x64`, `build:backend-mac-arm64`, `build:backend-mac-x64`, `build:backend-win`.
- Phase F1 (validation scripts): Created `scripts/verify-backend-payload.sh` and `scripts/verify-backend-payload.ps1`. They check structural layout, stdlib imports, third-party imports, and backend code imports.
- Phase F2 (tests): All 30 packaging path tests pass. Pre-existing failures in quiz router tests (7 collection errors from missing `capture_assets.py`, 11 quiz router 404s) and 5 frontend quiz tests are unrelated to packaging changes.
- Phase H (CI): Created `.github/workflows/release-build.yml` with matrix: `macos-latest` (arm64), `macos-13` (x64), `windows-latest` (x64). Draft release via `softprops/action-gh-release@v2`.

### 2026-04-06 — Node 20 deprecation fix in CI

- GitHub Actions deprecated Node.js 20 for JavaScript actions. Added `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true` env var to `.github/workflows/release-build.yml` so `actions/checkout@v4`, `actions/setup-node@v4`, `actions/upload-artifact@v4`, and `actions/download-artifact@v4` run on Node 24. Bumped `node-version` from `"20"` to `"22"` (current LTS) in all three build jobs. Once upstream v5 versions of these actions ship (natively targeting Node 24), the env var can be removed.

### 2026-04-07 — Pre-built ChromaDB bundling and per-source data management

- **Pre-built index:** Packaging scripts (`package-backend.sh`, `package-backend.ps1`) now run the CMG chunker after dependency installation to produce a pre-built ChromaDB index at `build/resources/data/chroma_db/`. This is bundled via `electron-builder.yml` `extraResources` as a read-only asset.
- **First-launch copy:** `seed.py` now checks for a bundled ChromaDB at `APP_ROOT/data/chroma_db/` before falling back to the chunker auto-seed. If the bundled DB exists and contains CMG data, it is copied to `CHROMA_DB_DIR` (user data). This eliminates the first-launch embedding delay in packaged builds.
- **Dev fallback:** In dev environments (no `STUDYBOT_APP_ROOT` set), `BUNDLED_CHROMA_DB_DIR` points to the same directory as `CHROMA_DB_DIR`, so the bundled check is a no-op and the existing auto-seed chunker runs as before.
- **Per-source clear:** `POST /settings/vector-store/clear` now accepts an optional `source_type` query parameter (`cmg`, `ref_doc`, `cpd_doc`, `notability_note`). Without it, the nuclear "delete entire chroma_db directory" behaviour is preserved. With it, only the specified source type is removed from the relevant collection.
- **Vector store status:** `GET /settings/vector-store/status` returns chunk counts per source type.
- **Settings UI:** The "CMG Data" and "Notes Pipeline" sections have been merged into a unified "Indexed Data" section showing per-source chunk counts and individual clear buttons.
- **Path constant:** Added `BUNDLED_CHROMA_DB_DIR` to `paths.py`.

### 2026-04-09 — Windows DLL-not-found fix

- **Symptom:** Windows personal build exits immediately with code 3221225781 (`0xC0000135` = `STATUS_DLL_NOT_FOUND`).
- **Root cause:** `package-backend.ps1` copied `python.exe`, `Lib/`, and `DLLs/` but missed the top-level DLLs (`python312.dll`, `python3.dll`, `vcruntime140.dll`, etc.) that sit alongside `python.exe` in the python-build-standalone distribution. Windows needs these in the same directory as the executable.
- **Fix:** Added a `Get-ChildItem -Filter "*.dll"` pass after copying executables to stage all top-level DLLs into the output directory.
- **Lesson:** The macOS script already had a `lib/libpython*.dylib` copy step, but the Windows equivalent was missing. When staging standalone Python runtimes, always verify that shared libraries (`.dll`/`.dylib`/`.so`) at the executable level are included.

### 2026-04-06 — Per-architecture Mac build fix

- Removed `arch` list from `electron-builder.yml` mac target. Previously both `arm64` and `x64` were listed, causing `npm run build:mac-x64` to produce DMGs for both architectures. Both DMGs bundled the same x64 backend payload because `build/resources/backend/` is overwritten per build. With the arch list removed, the CLI flag (`--arm64` or `--x64`) now controls which single arch gets built.
- Simplified Windows `nsis` target similarly (removed explicit `arch: [x64]`) for consistency. The `--win --x64` CLI flag already controls this.
- Builds must run sequentially. Between builds, rename or move the first DMG out of `release/` before running the next arch build to avoid payload overwrite issues.

## Rebuild Checklist

Run this checklist before cutting a new packaged app after major repo changes.

### Pre-build

- [ ] Re-read the decision log and known risks in this document.
- [ ] Confirm whether backend dependencies changed.
- [ ] Confirm whether Electron runtime paths or startup behaviour changed.
- [ ] Confirm whether new runtime assets must be bundled read-only.
- [ ] Confirm whether new writable state must be initialised under user data.
- [ ] Update this playbook for any new packaging-impacting decisions before building.

### Build

- [ ] Build or stage the backend payload for macOS.
- [ ] Build or stage the backend payload for Windows.
- [ ] Run the required tests affected by packaging changes.
- [ ] Build the macOS desktop artifact.
- [ ] Build the Windows desktop artifact.

### Validation

- [ ] Test first launch on macOS.
- [ ] Test first launch on Windows.
- [ ] Verify backend health and core app pages.
- [ ] Verify settings persistence.
- [ ] Verify runtime writes land under user data only.
- [ ] Record results and issues in this document.

### Release follow-through

- [ ] Update the verification matrix.
- [ ] Append new build notes and learnings.
- [ ] Append any new decision, rejection, or workaround to the decision log.
- [ ] If signing or CI changed, update the relevant sections here before closing the work.
