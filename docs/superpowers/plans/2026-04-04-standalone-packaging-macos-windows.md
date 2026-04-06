# Standalone macOS / Windows Packaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

## 1. Decision Summary

**Primary goal:** Produce installable, self-contained desktop packages for macOS and Windows that run without a pre-installed Python or manual `pip install`, by bundling the FastAPI backend and its native dependencies alongside the Electron shell.

**Chosen backend packaging approach:** **Embedded CPython + wheel tree**

- Bundle a platform-specific Python runtime plus installed backend dependencies under Electron `resources/backend/`.
- Keep the backend as regular Python files plus installed packages rather than freezing into a single binary.
- Treat PyInstaller/Nuitka as **deferred**. Do not spend implementation time on those paths for this release.

**Chosen application shape:** **Packaged desktop app**, not web app.

- Keep Electron as the product shell.
- Keep the local FastAPI backend on `127.0.0.1:7777`.
- Keep local persistence for ChromaDB, SQLite, and user settings.

**Release 1 scope**

- Installable app for macOS and Windows.
- Bundled Python runtime and backend dependencies.
- Bundled renderer build.
- Writable app state under the OS user-data directory.
- Bundled read-only seed content required for quiz, guidelines, settings, and search to work on first launch.
- Unsigned internal test builds may exist during implementation, but the intended public distribution path includes signing later.

**Release 1 non-goals**

- Web deployment.
- Re-architecting the backend into a hosted service.
- Shipping PyInstaller/Nuitka bundles.
- Universal packaging across every CPU architecture in the first pass.
- Bundling Playwright browser binaries in the default package.

## 2. Release Definition

This plan targets a **usable standalone desktop release**, not just a build that happens to open.

The release is considered complete when a user on a clean machine can:

- install the application without separately installing Python
- launch the app and have the backend start automatically
- open quiz, guidelines, settings, and search successfully on first run
- persist settings and study data across restarts
- use the app without writing into the installation directory

Pipeline/browser-refresh functionality is treated separately from the base standalone release.

## 3. Target Matrix

| Platform | Architecture | Output | Status |
|----------|--------------|--------|--------|
| macOS | `arm64` | `.dmg` | In scope for Release 1 |
| Windows | `x64` | `nsis` installer | In scope for Release 1 |
| macOS | `x64` or universal | Deferred | Out of scope for Release 1 |
| Windows | `arm64` | Deferred | Out of scope for Release 1 |
| Windows | portable build | Deferred | Out of scope for Release 1 |

If a broader target matrix is needed later, add it as a follow-up release after the first signed installers are working on clean machines.

## 4. Product Scope Decisions

These decisions are fixed for this plan and should not be reopened during implementation unless the user explicitly asks.

### 4.1 Bundled data

- Ship the read-only source data required by the app under the packaged app root.
- Store user-writable runtime data under the OS user-data directory.
- On first launch, copy or initialise writable files into user data only when required.

### 4.2 Pipeline features

- **Base standalone release:** packaged app does **not** include Playwright browser binaries.
- Pipeline features that depend on Playwright should be gated behind an explicit “download additional components” or equivalent later.
- The standalone packaging work in this plan must not block on pipeline-browser support.

### 4.3 Runtime configuration

- `config/settings.json` becomes user data owned at runtime.
- `config/settings.example.json` remains a read-only bundled default.
- Runtime API keys remain user-provided configuration.
- The packaged app should not depend on a repo-root `.env` file being present on an end-user machine.

## 5. Architecture Contract

### 5.1 Packaged directory layout

The packaged app should resolve to a layout conceptually equivalent to:

```text
resources/
  app.asar
  backend/
    bin/python            # macOS
    python.exe            # Windows
    Lib/ or lib/
    site-packages/ or equivalent installed tree
    app/
      src/python/...
  app-root/
    config/settings.example.json
    data/cmgs/...
    data/...              # other read-only bundled seeds required at runtime
```

The exact folder names may change, but the runtime contract must stay stable:

- Electron can spawn a real Python executable from disk.
- Python can locate its read-only bundled assets.
- Python can locate its writable user-data directory independently of install location.

### 5.2 Runtime environment contract

Electron must pass the following environment variables to the backend process:

- `STUDYBOT_USER_DATA`
- `STUDYBOT_APP_ROOT`
- `STUDYBOT_HOST`
- `STUDYBOT_PORT`
- `PYTHONPATH` as required by the bundled backend layout

### 5.3 Writable vs read-only paths

**Read-only bundled assets**

- packaged source defaults
- packaged CMG/reference data
- packaged backend code and dependencies

**Writable user-data assets**

- `settings.json`
- ChromaDB persistence
- SQLite mastery database
- logs
- any future downloaded browser/pipeline components

No runtime writes should target the application install directory.

## 6. Context the Implementer Must Read First

| Document / area | Why |
|-----------------|-----|
| `package.json` → `build` | Existing `appId`, `files`, `productName` |
| `src/electron/main.js` | `spawn("python3", ...)`, `process.resourcesPath`, production `dist` loading |
| `src/python/paths.py` | Existing root/data resolution must be centralised |
| `src/python/settings/router.py`, `src/python/llm/factory.py`, `src/python/llm/models.py` | Duplicate project-root assumptions must converge |
| `pyproject.toml` | Full backend dependency list for bundling |
| `CLAUDE.md` / `AGENTS.md` | Conventions; do not modify source originals in docs |

**Hard constraint:** Python cannot execute from inside `app.asar`. Place the backend under `extraResources` or otherwise ensure the spawned executable and import tree exist on disk outside `app.asar`.

## 7. Critical Path

Implement in this order. Do not start CI/signing work before the local packaged runtime works.

1. Centralise Python path/config resolution.
2. Make Electron spawn a bundled backend executable path in production.
3. Build the backend payload into a predictable `resources/backend` layout.
4. Configure Electron Builder to include backend and read-only app assets.
5. Seed first-run writable files and validate user-data behaviour.
6. Prove clean-machine installation on macOS and Windows.
7. Add signing/notarisation.
8. Add CI/release automation.

## 8. File Map

| Path | Responsibility |
|------|----------------|
| `src/python/paths.py` | Single source for `app_root`, `user_data_dir`, `data_dir`, `config_dir`, env overrides |
| `src/python/main.py` | Read bind host/port from env if needed |
| `src/python/settings/router.py` | Use `paths` for settings file location |
| `src/python/llm/factory.py`, `src/python/llm/models.py` | Use `paths` for config and runtime model discovery |
| `src/python/pipeline/run.py`, `src/python/pipeline/personal_docs/run.py` | Respect read-only bundled assets vs writable user-data paths |
| `src/electron/main.js` | Resolve backend executable; set `cwd`; pass env; handle platform paths |
| `package.json` or `electron-builder.yml` | `extraResources`, targets, artifact names, output directory |
| `scripts/package-backend.sh` / `scripts/package-backend.ps1` | Build platform-specific backend payload |
| `.github/workflows/release-build.yml` | Build matrix, artifact upload, optional release publish |
| `tests/python/test_paths_packaging.py` | Unit tests for packaged path resolution |

## 9. Execution Plan

### Phase A: Path and configuration model

**Objective:** make backend code independent of repo-root assumptions.

**Files**

- Modify: `src/python/paths.py`
- Modify: `src/python/settings/router.py`
- Modify: `src/python/llm/factory.py`
- Modify: `src/python/llm/models.py`
- Create: `tests/python/test_paths_packaging.py`

- [ ] **Step A1:** Extend `paths.py` to compute:
  - `APP_ROOT`: bundled read-only app root. In dev this resolves to the repo root; in packaged mode it is supplied by `STUDYBOT_APP_ROOT` or derived from the bundled layout.
  - `USER_DATA_DIR`: from `STUDYBOT_USER_DATA` when set; in packaged runs this must point to Electron `app.getPath("userData")`.
  - `DATA_DIR`: a stable child of `USER_DATA_DIR`.
  - `CONFIG_DIR`: a stable child of `USER_DATA_DIR`.
  - `CHROMA_DB_DIR`, `MASTERY_DB_PATH`, and other writable persistence paths under `USER_DATA_DIR`.

- [ ] **Step A2:** Remove duplicate local project-root discovery from settings and LLM modules. All runtime path resolution must flow from `paths.py`.

- [ ] **Step A3:** Make packaged runtime configuration depend on bundled defaults plus user-data overrides, not repo-local `.env` assumptions.

- [ ] **Step A4:** Add tests that set `STUDYBOT_USER_DATA` to a `tmp_path` and assert all writable DB/config paths stay under it.

- [ ] **Step A5:** Run `PYTHONPATH=src/python python3 -m pytest tests/python/test_paths_packaging.py -v`.

- [ ] **Step A6:** Run `PYTHONPATH=src/python python3 -m pytest tests/ -v` and fix regressions.

### Phase B: Electron main process

**Objective:** make production Electron spawn the bundled backend instead of `python3` on PATH.

**Files**

- Modify: `src/electron/main.js`

- [ ] **Step B1:** Introduce a helper such as `getBackendCommand()` returning `{ executable, args, cwd, env }`.

- [ ] **Step B2:** Development mode uses:
  - `executable = "python3"`
  - `args = [<repo>/src/python/main.py]`
  - `cwd = app.getAppPath()`

- [ ] **Step B3:** Production mode uses:
  - `executable = <resources>/backend/.../python(.exe)`
  - `args = [<resources>/backend/app/src/python/main.py]` or equivalent packaged backend entry
  - `cwd = process.resourcesPath` or another stable packaged path

- [ ] **Step B4:** Pass environment variables:
  - `STUDYBOT_USER_DATA=<app.getPath("userData")>`
  - `STUDYBOT_APP_ROOT=<bundled read-only app root>`
  - `STUDYBOT_HOST=127.0.0.1`
  - `STUDYBOT_PORT=7777`
  - `PYTHONPATH=<packaged backend import roots>`

- [ ] **Step B5:** Ensure Windows path handling works with spaces and absolute paths without requiring a shell.

- [ ] **Step B6:** Manual smoke test with a dry-run backend payload copied into `resources/backend`: `NODE_ENV=production electron .` reaches `/health`.

### Phase C: Backend payload build scripts

**Objective:** produce a repeatable platform-specific backend payload for Electron Builder.

**Files**

- Create: `scripts/package-backend.sh`
- Create: `scripts/package-backend.ps1`
- Create or modify: lockfile inputs for Python dependencies

- [ ] **Step C1:** Choose and commit a lockfile strategy for bundled Python dependencies.
  - Preferred: platform-specific lockfiles if native wheels differ.
  - The committed lockfile format must be CI-friendly and deterministic.

- [ ] **Step C2:** macOS packaging script:
  - download the selected embedded Python runtime for `arm64`
  - extract into a build staging directory
  - install locked dependencies into the staged runtime
  - copy backend application code into the staged payload
  - emit a final tree under `build/resources/backend`

- [ ] **Step C3:** Windows packaging script:
  - download the selected embedded Python runtime for `x64`
  - install locked dependencies into the staged runtime
  - copy backend application code into the staged payload
  - emit a final tree under `build/resources/backend`

- [ ] **Step C4:** Add a small validation step in each script that proves the staged runtime can import key modules such as `fastapi`, `uvicorn`, and `chromadb`.

### Phase D: First-run seeding and runtime data

**Objective:** ensure first launch creates only the writable files it needs under user data.

**Files**

- Modify: Electron first-run logic and/or Python startup path helpers

- [ ] **Step D1:** Choose one owner for first-run seeding logic: Electron or Python. Do not split responsibility across both.

- [ ] **Step D2:** On first launch, create `config/settings.json` under user data from bundled `config/settings.example.json` if it does not exist.

- [ ] **Step D3:** Seed any required writable runtime directories under user data.

- [ ] **Step D4:** Keep bundled CMG/reference assets read-only under the packaged app root unless copying is required for runtime mutation.

- [ ] **Step D5:** Explicitly document which datasets are bundled read-only and which are initialised writable.

### Phase E: Electron Builder configuration

**Objective:** build installable desktop artifacts that include the staged backend payload and bundled app assets.

**Files**

- Modify: `package.json` `build` section or create `electron-builder.yml`

- [ ] **Step E1:** Add `extraResources` for the staged backend payload.

- [ ] **Step E2:** Add bundled read-only app assets required at runtime.

- [ ] **Step E3:** Set `directories.output` to `release/`.

- [ ] **Step E4:** macOS target:
  - `dmg`
  - `arm64`

- [ ] **Step E5:** Windows target:
  - `nsis`
  - `x64`

- [ ] **Step E6:** Keep Python/runtime payload outside `app.asar`.

- [ ] **Step E7:** Run `npm run build` on each supported OS after backend staging and confirm `release/` contains the expected artifacts.

### Phase F: Verification

**Objective:** prove the packaged app works on clean machines before signing/CI work.

**Files**

- Create or modify only the tests/scripts needed for packaging validation

- [ ] **Step F1:** Add a minimal automated check that the staged backend layout exists and can import required modules.

- [ ] **Step F2:** Keep Python and renderer tests green after path/runtime changes.

- [ ] **Step F3:** Validate on a clean macOS machine with no system Python requirement.

- [ ] **Step F4:** Validate on a clean Windows machine with no system Python requirement.

### Phase G: Signing and notarisation

**Objective:** move from working installers to publicly distributable installers.

- [ ] **Step G1:** Apple:
  - enrol in Apple Developer Program
  - create Developer ID Application certificate
  - configure signing and notarisation secrets
  - confirm Gatekeeper allows launch on a clean Mac

- [ ] **Step G2:** Windows:
  - obtain Authenticode certificate
  - configure signing in Electron Builder
  - validate signed installer on a clean Windows machine

### Phase H: CI and release automation

**Objective:** make packaging reproducible after the local runtime path is proven.

**Files**

- Create: `.github/workflows/release-build.yml`

- [ ] **Step H1:** Trigger on `workflow_dispatch` and tags matching `v*`.

- [ ] **Step H2:** Build matrix:
  - `macos-latest` for macOS `arm64` artifact creation strategy
  - `windows-latest` for Windows `x64`

- [ ] **Step H3:** Each job:
  - checkout repo
  - set up Node
  - install frontend dependencies
  - run backend packaging script
  - run `npm run build`
  - upload `release/**` artifacts

- [ ] **Step H4:** Optionally publish a draft release after manual verification is trusted.

## 10. Acceptance Criteria

Release 1 is done when all of the following are true:

- [ ] macOS installer builds successfully for `arm64`
- [ ] Windows installer builds successfully for `x64`
- [ ] Neither packaged app requires a system Python installation
- [ ] Backend starts automatically on first launch and `/health` succeeds
- [ ] Quiz, guidelines, settings, and search load successfully on first run
- [ ] Settings persist across restart
- [ ] Writable runtime files are created under the OS user-data directory, not inside the install directory
- [ ] Clean-machine validation has been completed on both target platforms

## 11. Verification Matrix

| Check | macOS | Windows |
|-------|-------|---------|
| Install from artifact | | |
| No system Python installed | | |
| App launches and backend `/health` is OK | | |
| Quiz page loads | | |
| Guidelines page loads | | |
| Search works with bundled data | | |
| Settings persist across restart | | |
| Chroma / DB / config live under user data | | |
| Install directory remains read-only at runtime | | |
| Uninstall behaviour and retained user-data policy documented | | |

## 12. Risks and Deferred Work

These items are intentionally deferred unless the user asks to expand scope:

- bundling Playwright browser binaries
- pipeline refresh support in the default standalone package
- macOS universal builds
- Windows portable builds
- PyInstaller/Nuitka backend packaging
- auto-update infrastructure

## 13. Execution Handoff

**Plan complete and saved to** `docs/superpowers/plans/2026-04-04-standalone-packaging-macos-windows.md`.

**Recommended execution mode:** subagent-driven implementation, one critical-path task at a time, with review after each phase boundary.
