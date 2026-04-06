# Standalone Packaging — Phases A-E Design

**Date:** 2026-04-05
**Scope:** Phases A through E of the standalone packaging playbook (`Guides/standalone-packaging-macos-windows.md`)
**Isolation:** Git worktree on `feature/standalone-packaging` branch; current repo workspace untouched

---

## Workspace Setup

Create a git worktree at a sibling directory on branch `feature/standalone-packaging`. The worktree shares `.git` with the main repo but has its own working tree. All packaging work happens in the worktree. The current workspace at `studyBotcode/` is never modified.

When the work is complete, merge `feature/standalone-packaging` back to `main`.

---

## Phase A: Unified Path Resolution

### Problem

Three separate `PROJECT_ROOT` computations exist:

| File | Method | Value |
|------|--------|-------|
| `src/python/paths.py` | `Path(__file__).resolve().parents[2]` | `studyBotcode/` |
| `src/python/settings/router.py` | `Path(__file__).resolve().parents[3]` | `studyBotcode/` |
| `src/python/llm/factory.py` | `Path(__file__).resolve().parents[3]` | `studyBotcode/` |
| `src/python/pipeline/run.py` | `Path(__file__).resolve().parents[3]` | `studyBotcode/` |
| `src/python/pipeline/personal_docs/run.py` | `Path(__file__).resolve().parents[3]` | `studyBotcode/` |

All assume a repo-root directory layout that will not exist in a packaged app.

### Design

Extend `src/python/paths.py` to become the single source of truth for all runtime paths.

**Environment variables** (set by Electron in production, absent in dev):

| Variable | Purpose | Source in packaged app |
|----------|---------|------------------------|
| `STUDYBOT_USER_DATA` | Writable user-data root | `app.getPath('userData')` |
| `STUDYBOT_APP_ROOT` | Read-only bundled assets root | `process.resourcesPath` |
| `STUDYBOT_HOST` | Backend bind host | Default `127.0.0.1` |
| `STUDYBOT_PORT` | Backend bind port | Default `7777` |

**Path resolution logic in `paths.py`:**

```
If STUDYBOT_USER_DATA is set (packaged mode):
    USER_DATA_DIR = Path(STUDYBOT_USER_DATA)
    APP_ROOT = Path(STUDYBOT_APP_ROOT)
Else (dev mode):
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    USER_DATA_DIR = PROJECT_ROOT
    APP_ROOT = PROJECT_ROOT
```

**Exported constants:**

| Constant | Packaged mode | Dev mode |
|----------|---------------|----------|
| `APP_ROOT` | `$STUDYBOT_APP_ROOT` | `studyBotcode/` |
| `USER_DATA_DIR` | `$STUDYBOT_USER_DATA` | `studyBotcode/` |
| `DATA_DIR` | `USER_DATA_DIR / "data"` | `studyBotcode/data` |
| `CONFIG_DIR` | `USER_DATA_DIR / "config"` | `studyBotcode/config` |
| `SETTINGS_PATH` | `USER_DATA_DIR / "config/settings.json"` | `studyBotcode/config/settings.json` |
| `EXAMPLE_SETTINGS_PATH` | `APP_ROOT / "config/settings.example.json"` | `studyBotcode/config/settings.example.json` |
| `CHROMA_DB_DIR` | `USER_DATA_DIR / "data/chroma_db"` | `studyBotcode/data/chroma_db` |
| `MASTERY_DB_PATH` | `USER_DATA_DIR / "data/mastery.db"` | `studyBotcode/data/mastery.db` |
| `LOGS_DIR` | `USER_DATA_DIR / "logs"` | `studyBotcode/logs` |
| `HOST` | `$STUDYBOT_HOST` or `127.0.0.1` | `127.0.0.1` |
| `PORT` | `$STUDYBOT_PORT` or `7777` | `7777` |

**Changes to consumer files:**

- `src/python/settings/router.py`: Remove `_PROJECT_ROOT`, import `SETTINGS_PATH`, `EXAMPLE_SETTINGS_PATH` from `paths`
- `src/python/llm/factory.py`: Remove `_PROJECT_ROOT`, import `SETTINGS_PATH`, `EXAMPLE_SETTINGS_PATH` from `paths`
- `src/python/pipeline/run.py`: Remove `PROJECT_ROOT`, import `APP_ROOT`, `DATA_DIR`, `CHROMA_DB_DIR` from `paths`
- `src/python/pipeline/personal_docs/run.py`: Remove `PROJECT_ROOT`, import `APP_ROOT`, `DATA_DIR`, `CHROMA_DB_DIR` from `paths`
- `src/python/main.py`: Import `HOST`, `PORT` from `paths`; add `file://` and custom scheme to CORS origins

**Tests:**

Create `tests/python/test_paths_packaging.py`:
- Set `STUDYBOT_USER_DATA` to a temp directory
- Assert all writable paths (settings, chroma, mastery, logs) resolve under the temp directory
- Assert read-only paths (example settings, bundled data) resolve under `STUDYBOT_APP_ROOT`
- Assert dev-mode fallback still resolves to repo-root paths when env vars are absent

---

## Phase B: Electron Main Process

### Problem

`src/electron/main.js` spawns `python3` (system Python on PATH). No bundled interpreter support. CORS in `main.py` blocks `file://` origins used by the packaged frontend.

### Design

Add `getBackendCommand()` helper to `main.js`:

```js
function getBackendCommand() {
    if (isDev) {
        return {
            executable: "python3",
            args: [path.join(app.getAppPath(), "src/python/main.py")],
            cwd: app.getAppPath(),
            env: { PYTHONPATH: path.join(app.getAppPath(), "src/python") }
        };
    }
    const resourcesPath = process.resourcesPath;
    const isWin = process.platform === "win32";
    const pythonExe = isWin
        ? path.join(resourcesPath, "backend", "python.exe")
        : path.join(resourcesPath, "backend", "bin", "python");
    return {
        executable: pythonExe,
        args: [path.join(resourcesPath, "backend", "app", "src", "python", "main.py")],
        cwd: path.join(resourcesPath, "backend"),
        env: {
            STUDYBOT_USER_DATA: app.getPath("userData"),
            STUDYBOT_APP_ROOT: resourcesPath,
            STUDYBOT_HOST: "127.0.0.1",
            STUDYBOT_PORT: "7777",
            PYTHONPATH: path.join(resourcesPath, "backend", "app", "src", "python")
        }
    };
}
```

**CORS in `main.py`:**

Add `file://` origin to the CORS middleware. In packaged mode the frontend loads from `file://`, so the backend must accept requests from that origin. Alternatively, detect `STUDYBOT_USER_DATA` and use a permissive CORS policy for packaged builds.

---

## Phase C: Backend Payload Build Scripts

### Design

**macOS (`scripts/package-backend.sh`):**

- Accepts target architecture argument: `arm64` or `x64`
- Downloads the matching standalone CPython build from python.org (e.g. `python-3.12.x-macosx11.arm64` or `python-3.12.x-macosx11.x86_64`)
- Creates a clean virtual environment using the downloaded Python
- Installs backend dependencies from requirements
- Stages the installed tree plus `src/python/` into `build/resources/backend-mac-<arch>/`
- Validates by running an import check: `fastapi`, `uvicorn`, `chromadb`
- Output structure:
  ```
  build/resources/backend-mac-arm64/
    bin/python
    lib/python3.12/site-packages/...
    app/src/python/...
  ```

**Windows (`scripts/package-backend.ps1`):**

- Downloads embedded CPython for Windows x64 from python.org
- Installs backend dependencies via `pip install --target`
- Copies `src/python/` into the staged tree
- Emits `build/resources/backend-win-x64/`
- Validates with same import check
- Output structure:
  ```
  build/resources/backend-win-x64/
    python.exe
    Lib/site-packages/...
    app/src/python/...
  ```

---

## Phase D: First-Run Seeding

### Design

Python-side ownership. The backend checks on startup (in `main.py` or a dedicated module).

**Seeding logic (on every startup):**

1. Check if `SETTINGS_PATH` (`user_data/config/settings.json`) exists
2. If not, copy from `EXAMPLE_SETTINGS_PATH` (`app_root/config/settings.example.json`)
3. Ensure writable directories exist: `data/chroma_db/`, `data/`, `logs/`
4. Do not overwrite existing files

**Read-only bundled assets** remain under `APP_ROOT`:
- CMG data: `APP_ROOT/data/cmgs/`
- Reference docs: bundled as needed
- Example settings: `APP_ROOT/config/settings.example.json`

**Writable user-data assets** under `USER_DATA_DIR`:
- `config/settings.json`
- `data/chroma_db/`
- `data/mastery.db`
- `logs/`

---

## Phase E: Electron Builder Configuration

### Design

Move build configuration from inline `package.json` to `electron-builder.yml`.

```yaml
appId: com.studybot.clinical-recall
productName: Clinical Recall Assistant
directories:
  output: release/
files:
  - dist/**/*
  - src/electron/**/*
extraResources:
  - from: build/resources/backend
    to: backend
    filter:
      - "**/*"
  - from: config/settings.example.json
    to: config/settings.example.json
  - from: data/cmgs
    to: data/cmgs
    filter:
      - "**/*"
mac:
  category: public.app-category.education
  target:
    - target: dmg
      arch:
        - arm64
        - x64
win:
  target:
    - target: nsis
      arch:
        - x64
asar: true
asarUnpack:
  - "**/*.node"
```

**Key constraints:**
- Python runtime payload stays outside `app.asar` via `extraResources`
- Each macOS arch build includes only its matching backend payload
- The `files` array keeps the renderer build and Electron main process
- `extraResources` adds the backend payload, config defaults, and bundled data

---

## Dev Mode Compatibility

All changes preserve dev-mode behaviour when packaging env vars are absent:
- `paths.py` falls back to repo-root paths
- `main.js` continues spawning `python3` with repo paths
- CORS keeps existing localhost origins
- Existing tests pass unchanged

---

## Files Changed (Summary)

| File | Action | Phase |
|------|--------|-------|
| `src/python/paths.py` | Extend with env-var-driven resolution | A |
| `src/python/settings/router.py` | Remove duplicate root, import from paths | A |
| `src/python/llm/factory.py` | Remove duplicate root, import from paths | A |
| `src/python/llm/models.py` | Import paths if needed | A |
| `src/python/pipeline/run.py` | Remove duplicate root, import from paths | A |
| `src/python/pipeline/personal_docs/run.py` | Remove duplicate root, import from paths | A |
| `src/python/main.py` | Import host/port from paths, add file:// CORS | A+B |
| `tests/python/test_paths_packaging.py` | Create | A |
| `src/electron/main.js` | Add getBackendCommand, pass env vars | B |
| `scripts/package-backend.sh` | Create | C |
| `scripts/package-backend.ps1` | Create | C |
| `electron-builder.yml` | Create (migrate from package.json) | E |
| `package.json` | Remove inline build config | E |

---

## Success Criteria

- All existing Python and frontend tests pass in the worktree
- `PYTHONPATH=src/python python3 -m pytest tests/python/test_paths_packaging.py -v` passes
- `PYTHONPATH=src/python python3 -m pytest tests/ -v` passes with no regressions
- Dev mode (`npm run dev`) works identically to the main branch
- `NODE_ENV=production electron .` can reach `/health` when a staged backend payload is present
- Build scripts produce valid backend payloads for each target platform
- `npm run build` produces expected artifacts under `release/` for at least one macOS arch
