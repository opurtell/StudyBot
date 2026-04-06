# Standalone Packaging — Remaining Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Date:** 2026-04-06
**Supersedes:** Phases F-H of `Guides/standalone-packaging-macos-windows.md` (this plan provides the detailed implementation steps; the playbook remains the living source of truth for decisions and status).

**Context:** Phases A-E are complete on paper. Path resolution, Electron spawn logic, seeding, builder config, and packaging scripts exist. However, code review reveals several gaps that will prevent the packaged app from running on a clean machine. This plan addresses those gaps (Phase P), then proceeds through verification (Phase F), signing (Phase G), and CI (Phase H).

**Architecture:** Electron 32 + React 19 + Vite 6 (renderer), FastAPI on 127.0.0.1:7777 (backend), ChromaDB (vector store), embedded CPython (bundled runtime).

**Tech Stack:** TypeScript/JavaScript (Electron main), Python 3.10+ (backend), shell/PowerShell (packaging scripts), GitHub Actions (CI).

---

## Execution dependency graph

```
Phase P (prerequisite fixes)
  P1 ──┐
  P2   │
  P3 ──┤
  P4   │
  P5 ──┼── Phase F (verification)
  P6 ──┘      F1 → F2 → (F3, F4, F5 when machines available)
                                ↓
                              Phase H (CI/release automation)
                                H1 → H2 → H3 → H4

Phase G (signing) — DEFERRED
  Requires Apple Developer Program and Windows Authenticode certificates.
  Revisit after Phase F validation confirms clean-machine runtime is solid.
```

---

## Phase P: Prerequisite Fixes

Phases A-E left gaps that will cause runtime failures. These must be resolved before any clean-machine verification.

### P1: Generate `requirements.txt` from `pyproject.toml`

**Problem:** Both `scripts/package-backend.sh` and `scripts/package-backend.ps1` check for `requirements.txt` and silently skip dependency installation when absent. The file does not exist; dependencies are declared in `pyproject.toml`. The staged backend payload would ship with zero third-party packages (no FastAPI, no ChromaDB, no uvicorn).

**Approach:** Generate `requirements.txt` from `pyproject.toml` using `pip` or `uv`, and make the packaging scripts call this generation step.

**Files:**
- Create: `scripts/generate-requirements.sh`
- Create: `scripts/generate-requirements.ps1`
- Modify: `scripts/package-backend.sh`
- Modify: `scripts/package-backend.ps1`

- [x] **P1.1:** Create `scripts/generate-requirements.sh` that runs `pip install --dry-run .` or `uv pip compile pyproject.toml` to emit a pinned `requirements.txt` into the repo root. Must exclude `dev` extras. Must work offline if dependencies are already cached (for CI determinism).
- [x] **P1.2:** Create `scripts/generate-requirements.ps1` with equivalent logic for Windows.
- [x] **P1.3:** Modify `package-backend.sh` to call `generate-requirements.sh` before the venv step, so `requirements.txt` always exists at install time. Alternatively, change the install step to use `pip install .` or `uv pip install .` from `pyproject.toml` directly into `--target`, removing the `requirements.txt` intermediary entirely.
- [x] **P1.4:** Same change for `package-backend.ps1`.
- [x] **P1.5:** Add `requirements.txt` to `.gitignore` (it is a generated artefact, not a source file).

**Acceptance:** Running `scripts/package-backend.sh arm64` on a machine with the project's Python dependencies available produces a payload where `lib/fastapi/`, `lib/uvicorn/`, `lib/chromadb/` all exist.

---

### P2: Fix build-script output path to match electron-builder expectations

**Problem:** `package-backend.sh` renames staging to `build/resources/backend-mac-<arch>/`. `package-backend.ps1` renames to `build/resources/backend-win-x64/`. But `electron-builder.yml` declares `extraResources.from: build/resources/backend`. There is no step that copies or renames the arch-specific payload to the expected location.

**Approach:** Change the packaging scripts to output directly to `build/resources/backend/` (the location electron-builder expects). The architecture-specific naming is unnecessary because only one architecture's payload is staged per build invocation.

**Files:**
- Modify: `scripts/package-backend.sh`
- Modify: `scripts/package-backend.ps1`

- [x] **P2.1:** In `package-backend.sh`, change the final output directory from `$REPO_ROOT/build/resources/backend-mac-$ARCH` to `$REPO_ROOT/build/resources/backend`. Remove the old arch-specific directory on start to avoid stale payload mixing.
- [x] **P2.2:** In `package-backend.ps1`, change the final output directory from `build\resources\backend-win-x64` to `build\resources\backend`.
- [x] **P2.3:** Verify `electron-builder.yml` `extraResources.from: build/resources/backend` now matches the packaging script output. No change needed in the yml.
- [x] **P2.4:** Confirm the directory structure inside `build/resources/backend/` matches what `main.js` expects at runtime:
  - macOS: `bin/python` (or `bin/python3`), `lib/`, `app/src/python/`
  - Windows: `python.exe` (at `python/python.exe` in the current script — need to verify this matches `main.js` which looks for `<resources>/backend/python.exe`)

**Acceptance:** Running `scripts/package-backend.sh arm64` produces `build/resources/backend/` with the correct layout. Running `npm run build` after staging picks up the payload.

**Note on Windows path mismatch:** `main.js:107` looks for `<resources>/backend/python.exe` directly. But `package-backend.ps1:44` copies `python.exe` to `<staging>/python/python.exe`, which would land at `<resources>/backend/python/python.exe`. This needs to be reconciled — either move the exe to the backend root or update `main.js`.

---

### P3: Download standalone/embeddable Python instead of using host Python

**Problem:** Both packaging scripts create a venv from the host system's Python and copy the binary out. This produces a Python executable that depends on the host's shared libraries and stdlib installation. It will not work on a clean machine.

**Approach:** Download platform-appropriate standalone Python distributions.

| Platform | Source | Architecture handling |
|----------|--------|-----------------------|
| macOS | [python-build-standalone](https://github.com/indygreg/python-build-standalone/releases) — `cpython-3.12.*-{arch}-apple-darwin-install_only.tar.gz` | Download the matching `aarch64` or `x86_64` tarball |
| Windows | [python-build-standalone](https://github.com/indygreg/python-build-standalone/releases) — `cpython-3.12.*-x86_64-pc-windows-msvc-install_only.tar.gz` | Download x86_64 tarball |

The `install_only` distributions contain a complete Python install with stdlib, suitable for bundling.

**Files:**
- Modify: `scripts/package-backend.sh`
- Modify: `scripts/package-backend.ps1`

- [x] **P3.1:** In `package-backend.sh`, replace the venv-creation block with a download-and-extract step that:
  1. Computes the python-build-standalone download URL for the requested arch (`aarch64` for arm64, `x86_64` for x64) and Python version
  2. Downloads the `install_only.tar.gz` (cache it in a temp location to avoid re-downloading)
  3. Extracts the Python installation (contains `bin/python3`, `lib/python3.12/`, etc.)
  4. Stages it into the payload layout: binary to `bin/`, stdlib to `lib/`
- [x] **P3.2:** In `package-backend.ps1`, same approach for Windows x64:
  1. Download the `install_only.tar.gz` for x86_64-pc-windows-msvc
  2. Extract and stage: `python.exe` and `python3.exe` to the payload root, stdlib to `Lib/`
- [x] **P3.3:** After staging the standalone Python, install pip packages into the payload using the staged Python binary with `--target` (not via a venv). The standalone distributions include `pip`.
- [x] **P3.4:** Validate that the staged Python binary runs independently (no references to the host's `/usr/local/lib/python*` or `C:\Python*`).

**Acceptance:** The staged `bin/python3` (macOS) or `python.exe` (Windows) can import `os`, `sys`, `json`, and all installed third-party packages without any host Python installation.

---

### P4: Bundle Python standard library

**Problem:** Even with standalone Python downloads, the current scripts don't explicitly verify or configure the stdlib location. macOS expects `lib/python3.12/` (or similar) to be importable. Windows needs the stdlib ZIP or directory. If `PYTHONPATH` in `main.js` only points to `app/src/python` and the installed-packages dir, stdlib modules won't be found unless the Python binary knows where its own stdlib is.

**Approach:** The python-build-standalone `install_only` distributions include the stdlib in the correct relative position. After extracting, verify the layout and ensure `sys.prefix` resolves correctly so the binary can find its own stdlib.

**Files:**
- Modify: `scripts/package-backend.sh`
- Modify: `scripts/package-backend.ps1`
- Potentially modify: `src/electron/main.js` (if PYTHONPATH needs to include stdlib)

- [x] **P4.1:** After extracting the standalone Python in the macOS script, verify the expected layout:
  - `bin/python3` exists and is executable
  - `lib/python3.12/` exists and contains stdlib modules (`os.py`, `json/`, etc.)
  - Running `./bin/python3 -c "import os; print(os.__file__)"` shows it importing from the staged `lib/` directory
- [x] **P4.2:** Same verification for Windows:
  - `python.exe` exists
  - `Lib/` exists with stdlib modules
  - Running `.\python.exe -c "import os; print(os.__file__)"` shows the staged `Lib/`
- [x] **P4.3:** If the standalone Python's `sys.prefix` does not point to the staged directory (i.e., it still references the build-time prefix), set `PYTHONHOME` in the Electron spawn env to the backend payload root so Python can find its stdlib. Add to `main.js` production env:
  ```
  PYTHONHOME: path.join(resourcesPath, "backend")
  ```
- [x] **P4.4:** Test that the staged Python can import stdlib modules, installed packages, and backend code with the exact `PYTHONPATH` and `PYTHONHOME` that Electron will set.

**Acceptance:** The staged Python binary imports `os`, `sys`, `json` (stdlib), `fastapi` (installed), and `main` (backend code) using only the env vars that `main.js` sets in production mode.

---

### P5: Fix bare relative paths in backend routers

**Problem:** Several backend routers use bare relative paths like `Path("data/cmgs/structured")` which resolve against the Python process's CWD. In packaged mode, the CWD is `<resources>/backend/` but the data lives under `<resources>/` (at `APP_ROOT`). The `paths.py` module correctly resolves `DATA_DIR` and `APP_ROOT`, but these routers don't use it.

**Routers affected (identified by code search):**
- `src/python/guidelines/router.py` — scans `data/cmgs/structured/` for guideline JSON files
- `src/python/medication/router.py` — reads medication data from `data/cmgs/structured/`
- `src/python/sources/router.py` (if it exists) — scans source document directories

**Approach:** Replace bare relative paths with `paths.py` constants. For read-only bundled data (CMG structured JSON), use `APP_ROOT`-based paths. For writable data (ChromaDB, mastery DB), paths are already correct.

**Files:**
- Modify: `src/python/paths.py`
- Modify: `src/python/guidelines/router.py`
- Modify: `src/python/medication/router.py`
- Modify: `src/python/sources/router.py` (if it exists)
- Modify: `tests/python/test_paths_packaging.py`

- [x] **P5.1:** Add a `CMG_STRUCTURED_DIR` constant to `paths.py` that resolves to `APP_ROOT / "data" / "cmgs" / "structured"` in packaged mode (read-only bundled data) and `PROJECT_ROOT / "data" / "cmgs" / "structured"` in dev mode.
- [x] **P5.2:** Add any other path constants needed by routers (e.g., `REFDOCS_DIR`, `CPDDOCS_DIR`, `PERSONAL_DOCS_DIR`).
- [x] **P5.3:** Update `guidelines/router.py` to use the new path constants instead of bare `Path("data/cmgs/structured")`.
- [x] **P5.4:** Update `medication/router.py` similarly.
- [x] **P5.5:** Update `sources/router.py` (or equivalent) similarly.
- [x] **P5.6:** Add packaging-mode tests that verify these paths resolve under `APP_ROOT` when env vars are set.
- [x] **P5.7:** Run `PYTHONPATH=src/python python3 -m pytest tests/ -v` and fix regressions.

**Acceptance:** All routers resolve data paths through `paths.py`. In packaged mode, CMG data paths point to `STUDYBOT_APP_ROOT/data/cmgs/structured/`. In dev mode, they point to the repo root.

---

### P6: Bundle CMG structured data as read-only assets

**Problem:** `data/cmgs/` is empty in the repo (gitignored). The `/guidelines` and `/medication/doses` endpoints return empty results without this data. The acceptance criteria require that guidelines and search "load successfully on first run." The packaged app must ship pre-built CMG data.

**Approach:** Before building the packaged app, run the CMG extraction pipeline to generate `data/cmgs/structured/`. Include this data in the `extraResources` of electron-builder as a read-only bundled asset.

**Files:**
- Modify: `electron-builder.yml`
- Potentially create: `scripts/build-cmg-data.sh` (or document the manual step)

- [x] **P6.1:** Run the CMG pipeline to generate `data/cmgs/structured/` with all guidelines, medication, and clinical skills JSON files.
- [x] **P6.2:** Add `extraResources` entry in `electron-builder.yml` for CMG data:
  ```yaml
  - from: data/cmgs/structured
    to: data/cmgs/structured
    filter:
      - "**/*.json"
  ```
- [x] **P6.3:** Verify that `APP_ROOT / "data" / "cmgs" / "structured"` (from `paths.py`) maps to `<resourcesPath>/data/cmgs/structured/` in the packaged layout.
- [x] **P6.4:** Consider whether pre-built ChromaDB collections should also be bundled. If quiz and search should work on first launch without the user running the pipeline, the vector store must be pre-populated. If not, document that quiz and search require the user to run the pipeline first, and update the acceptance criteria accordingly.
- [x] **P6.5:** Document the exact list of bundled read-only assets in the playbook.

**Acceptance:** A freshly installed packaged app can load `/guidelines` and `/medication/doses` and return data on first launch without any user action.

**Decision required:** Should pre-built ChromaDB collections be bundled, or is an empty search/quiz acceptable on first launch? This affects the data seeding strategy and the first-run user experience. The playbook's "known unknowns" section flags this.

---

### P7: Add build orchestration npm scripts

**Problem:** Building a packaged app currently requires manual steps: (1) generate requirements, (2) run packaging script, (3) run `npm run build`. There is no single command, and the `npm run build` script does not include backend staging.

**Approach:** Add npm scripts that orchestrate the full build pipeline.

**Files:**
- Modify: `package.json`

- [x] **P7.1:** Add `build:backend-mac` script: `bash scripts/package-backend.sh arm64 && bash scripts/package-backend.sh x64` (or accept an arch argument).
- [x] **P7.2:** Add `build:backend-win` script: `pwsh -File scripts/package-backend.ps1`.
- [x] **P7.3:** Add `build:mac-arm64` script: `npm run build:backend-mac-arm64 && vite build && electron-builder --arm64`.
- [x] **P7.4:** Add `build:mac-x64` script: `npm run build:backend-mac-x64 && vite build && electron-builder --x64`.
- [x] **P7.5:** Add `build:win-x64` script: `npm run build:backend-win && vite build && electron-builder --win --x64`.
- [x] **P7.6:** Consider adding a `build:all` script for CI that runs the appropriate target based on the platform.

**Acceptance:** Running `npm run build:mac-arm64` on macOS produces a complete `.dmg` in `release/` with the backend payload embedded.

---

## Phase F: Verification

**Objective:** Prove packaged apps work on clean machines before signing and CI work.

### F1: Automated staged-backend validation

**Files:**
- Create: `scripts/verify-backend-payload.sh`
- Create: `scripts/verify-backend-payload.ps1`

- [x] **F1.1:** Create `scripts/verify-backend-payload.sh` that:
  1. Checks `build/resources/backend/` exists
  2. Checks `bin/python3` (macOS) or `python.exe` (Windows) exists and is executable
  3. Checks stdlib is importable (`import os, sys, json`)
  4. Checks third-party packages are importable (`import fastapi, uvicorn, chromadb`)
  5. Checks backend code is importable (`import main`)
  6. Exits non-zero on any failure with a clear error message
- [x] **F1.2:** Create `scripts/verify-backend-payload.ps1` with equivalent checks for Windows.
- [x] **F1.3:** Integrate the verification script into the packaging scripts (run automatically after staging) and into `npm run build` (run before electron-builder).

**Acceptance:** `scripts/verify-backend-payload.sh` exits 0 when the payload is correctly staged, and exits non-zero with a useful error when something is missing.

---

### F2: Keep Python and renderer tests green

- [x] **F2.1:** Run `PYTHONPATH=src/python python3 -m pytest tests/ -v` after every packaging change and fix regressions immediately.
- [x] **F2.2:** Run `npx vitest run` after every renderer or Electron change.
- [x] **F2.3:** Run `npx tsc --noEmit` after every TypeScript change.

**Acceptance:** All three test suites pass cleanly after packaging changes.

---

### F3-F5: Clean-machine validation

These steps require physical or virtual machines with no Python installed. They cannot be automated without dedicated test infrastructure.

- [ ] **F3:** Validate the `arm64` macOS build on a clean Apple Silicon machine:
  1. Install from `.dmg`
  2. Launch app — backend starts, `/health` returns 200
  3. Quiz page loads (may be empty if ChromaDB not bundled)
  4. Guidelines page loads and shows CMG data
  5. Settings page loads and persists a change across restart
  6. Search page loads (may return empty if ChromaDB not bundled)
  7. Confirm no writes to `/Applications/Clinical Recall Assistant.app/`
  8. Confirm writable data lands in `~/Library/Application Support/clinical-recall-assistant/`
  9. Uninstall and confirm user data policy (retained or cleaned up)
- [ ] **F4:** Same validation for `x64` macOS build on an Intel Mac.
- [ ] **F5:** Same validation for Windows `x64` NSIS installer:
  - Writable data should land in `%APPDATA%/Clinical Recall Assistant/`
  - Confirm no writes to `C:\Program Files\Clinical Recall Assistant\`

**Acceptance:** The verification matrix in the playbook is updated with pass/fail for every check on every platform.

---

## Phase G: Signing and Notarisation — DEFERRED

**Status:** Deferred until Apple Developer Program and Windows Authenticode certificates are obtained. Unsigned internal test builds are acceptable per the Release 1 scope in the playbook.

**Rationale:** Phase F clean-machine validation must confirm the runtime works before investing in signing. Signing can be added to an established build pipeline without changing packaging logic.

**When revisiting, the steps are:**

### G1: macOS signing and notarisation

- [ ] **G1.1:** Enrol in Apple Developer Program ($99/year).
- [ ] **G1.2:** Obtain a Developer ID Application certificate (via Xcode > Settings > Accounts, or `security import` from a `.p12` file).
- [ ] **G1.3:** Add signing configuration to `electron-builder.yml`:
  ```yaml
  mac:
    identity: "Developer ID Application: <Your Name> (<Team ID>)"
    hardenedRuntime: true
    entitlements: "build/entitlements.mac.plist"
    entitlementsInherit: "build/entitlements.mac.plist"
  ```
- [ ] **G1.4:** Create `build/entitlements.mac.plist` with the minimum entitlements (network server for localhost, file access for user data).
- [ ] **G1.5:** Configure notarisation. Either:
  - Use `electron-notarize` package, or
  - Use electron-builder's built-in notarisation via `APPLE_ID`, `APPLE_APP_SPECIFIC_PASSWORD`, and `APPLE_TEAM_ID` environment variables.
- [ ] **G1.6:** Store signing and notarisation secrets in GitHub Actions secrets (for Phase H) or in a secure local vault.
- [ ] **G1.7:** Build a signed and notarised DMG. Validate on a clean Mac with Gatekeeper enabled: double-click the DMG, drag to Applications, launch — should open without the "unidentified developer" warning.
- [ ] **G1.8:** Update the playbook decision log with the signing approach and any issues.

### G2: Windows Authenticode signing

- [ ] **G2.1:** Purchase a Windows code-signing certificate (OV or EV). OV is cheaper but triggers SmartScreen warnings for unknown publishers. EV avoids SmartScreen but requires a hardware token.
- [ ] **G2.2:** Add signing configuration to `electron-builder.yml`:
  ```yaml
  win:
    certificateFile: "build/cert.pfx"
    sign: "build/sign-windows.js"
  ```
  Or use `CSC_LINK` environment variable with a base64-encoded PFX.
- [ ] **G2.3:** Create `build/sign-windows.js` if custom signing logic is needed (e.g., for EV tokens), or use electron-builder's default signtool integration.
- [ ] **G2.4:** Build a signed Windows NSIS installer. Validate on a clean Windows machine: no "Unknown Publisher" warning (OV cert) or no SmartScreen blue box (EV cert).
- [ ] **G2.5:** Update the playbook decision log with the signing approach.

---

## Phase H: CI and Release Automation

**Objective:** Make packaging reproducible once local packaged runtime behaviour is proven.

### H1: Create release-build workflow

**Files:**
- Create: `.github/workflows/release-build.yml`

- [x] **H1.1:** Create the workflow file with triggers:
  ```yaml
  on:
    push:
      tags:
        - "v*"
    workflow_dispatch:
      inputs:
        version:
          description: "Version tag (e.g. v0.1.0)"
          required: false
  ```

---

### H2: Build matrix

- [x] **H2.1:** Define a strategy matrix:
  ```yaml
  strategy:
    matrix:
      include:
        - os: macos-latest
          arch: arm64
        - os: macos-13
          arch: x64
        - os: windows-latest
          arch: x64
  ```
  Note: `macos-latest` is Apple Silicon (arm64). `macos-13` is Intel (x64). This requires investigation — confirm that `macos-13` runners are available and that electron-builder can produce the correct arch from each runner.
- [x] **H2.2:** Investigate whether macOS x64 builds can be produced on an arm64 runner using `electron-builder --x64` with cross-compilation, or whether a dedicated Intel runner is required. Document the decision.

---

### H3: Job steps

- [x] **H3.1:** Each job runs:
  1. `actions/checkout@v4`
  2. `actions/setup-node@v4` with Node 20+
  3. `npm ci`
  4. Backend packaging script for the target platform/arch
  5. Verify backend payload
  6. `npm run build` (or arch-specific build command)
  7. Upload `release/**` as artefacts using `actions/upload-artifact@v4`
- [x] **H3.2:** macOS jobs need Python available for the backend packaging script. Use `actions/setup-python@v5` or ensure the packaging script downloads standalone Python independently (per P3).
- [x] **H3.3:** Builds are unsigned (Phase G deferred). No signing secrets are needed in CI at this stage. When signing is re-enabled, add `CSC_LINK`, `CSC_KEY_PASSWORD`, `APPLE_ID`, `APPLE_APP_SPECIFIC_PASSWORD`, `APPLE_TEAM_ID` (macOS) and `CSC_LINK`, `CSC_KEY_PASSWORD` (Windows) as GitHub Actions secrets.

---

### H4: Draft release

- [x] **H4.1:** Add a final job (after all build jobs succeed) that creates a draft GitHub Release:
  ```yaml
  - name: Create draft release
    uses: softprops/action-gh-release@v2
    with:
      draft: true
      files: release/**
  ```
- [x] **H4.2:** Tag the release with the version from the trigger tag or workflow input.
- [x] **H4.3:** Manual review step: the draft release is not published automatically. A human reviews the artefacts and publishes manually.

**Acceptance:** Pushing a `v*` tag or triggering the workflow manually produces artefacts for all three targets (macOS arm64, macOS x64, Windows x64) and creates a draft GitHub Release.

---

## Acceptance Criteria (from playbook)

These are the final acceptance criteria for the full standalone packaging work. All must pass before the release is considered complete.

- [ ] macOS installer builds successfully for `arm64`
- [ ] macOS installer builds successfully for `x64`
- [ ] Windows installer builds successfully for `x64`
- [ ] Neither packaged app requires a system Python installation
- [ ] Backend starts automatically on first launch and `/health` succeeds
- [ ] Quiz, guidelines, settings, and search load successfully on first run
- [ ] Settings persist across restart
- [ ] Writable runtime files are created under the OS user-data directory, not inside the install directory
- [ ] Clean-machine validation has been completed on Apple Silicon macOS, Intel macOS, and Windows

---

## Decisions Required Before Implementation

| ID | Question | Options | Default |
|----|----------|---------|---------|
| D1 | Should pre-built ChromaDB collections be bundled for first-launch search/quiz? | Bundle pre-built collections / Ship empty, require user pipeline run / Bundle CMG collections only, defer personal docs | Bundle CMG collections only (search works for guidelines, not personal notes) |
| D2 | How to generate `requirements.txt`? | `pip-compile` (pip-tools) / `uv pip compile` / `pip install --dry-run` / Install directly from `pyproject.toml` with `--target` | Install directly from `pyproject.toml` (simpler, avoids lockfile maintenance) |
| D3 | Windows Python exe location in payload? | `<backend>/python.exe` (flat) / `<backend>/python/python.exe` (subdirectory) | `<backend>/python.exe` (matches current `main.js` expectation) |
| D4 | CI runner for macOS x64 builds? | `macos-13` runner (Intel) / Cross-compile on `macos-latest` (arm64) | Investigate and decide in H2 |

---

## Risks and Open Questions

1. **python-build-standalone URL stability:** The download URLs for standalone Python may change between releases. Pin to a specific release tag and cache the tarball in CI.
2. **Native dependencies:** Some Python packages (e.g., `chromadb` may have native extensions) must match the target architecture. Installing packages using the staged target-arch Python binary (not the host Python) ensures compatibility.
3. **macOS x64 on arm64 runners:** Cross-compilation may produce a working Electron app but the bundled Python runtime must be a genuine x86_64 binary, not an arm64 binary. The packaging script must download the correct arch regardless of the host.
4. **Payload size:** A full Python runtime plus dependencies (FastAPI, ChromaDB, etc.) may produce a large installer. Monitor size and consider stripping unnecessary files (`__pycache__`, `.dist-info`, tests) in the packaging scripts.
5. **First-launch experience:** If ChromaDB is empty, quiz and search will return nothing. The UI should handle this gracefully (empty states, prompts to run the pipeline) rather than showing errors.
6. **Playwright dependency:** `playwright` is listed in `pyproject.toml` dependencies but browser binaries are excluded from the standalone package. The import will succeed but browser-dependent features will fail. Consider making `playwright` an optional dependency or gating pipeline features at runtime.
