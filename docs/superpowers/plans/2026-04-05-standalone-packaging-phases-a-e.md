# Standalone Packaging Phases A-E Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the app buildable as a standalone desktop application for macOS and Windows with bundled Python, no system Python dependency, and no writes to the install directory.

**Architecture:** Extend `paths.py` to support env-var-driven path resolution for packaged mode, update Electron's main process to spawn a bundled Python interpreter, create backend payload build scripts, add first-run seeding logic, and configure electron-builder to produce installable artifacts. A git worktree on `feature/standalone-packaging` provides isolation from the main workspace.

**Tech Stack:** Python 3.10+, Electron 32, electron-builder 25, Vite 6, FastAPI, ChromaDB

---

## Pre-Task: Create git worktree

**Files:**
- None (git operations only)

- [ ] **Step 1: Create the worktree**

Run from the main repo directory:

```bash
git worktree add ../StudyBot-packaging -b feature/standalone-packaging
```

Expected: New directory `../StudyBot-packaging/` created on branch `feature/standalone-packaging`.

- [ ] **Step 2: Verify the worktree**

```bash
cd ../StudyBot-packaging && git branch --show-current
```

Expected: `feature/standalone-packaging`

- [ ] **Step 3: Verify dev tests pass in worktree**

```bash
PYTHONPATH=src/python python3 -m pytest tests/ -v
```

Expected: All existing tests pass.

---

## Task 1: Extend `paths.py` with env-var-driven resolution

**Files:**
- Modify: `src/python/paths.py`
- Create: `tests/python/test_paths_packaging.py`

- [ ] **Step 1: Write the failing test for packaged-mode path resolution**

Create `tests/python/test_paths_packaging.py`:

```python
import os
from pathlib import Path
from unittest.mock import patch

import pytest


def _reload_paths():
    import importlib
    import paths
    importlib.reload(paths)
    return paths


class TestPackagedMode:
    def test_user_data_dir_from_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STUDYBOT_USER_DATA", str(tmp_path / "userdata"))
        monkeypatch.setenv("STUDYBOT_APP_ROOT", str(tmp_path / "approot"))
        paths = _reload_paths()
        assert paths.USER_DATA_DIR == tmp_path / "userdata"

    def test_app_root_from_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STUDYBOT_USER_DATA", str(tmp_path / "userdata"))
        monkeypatch.setenv("STUDYBOT_APP_ROOT", str(tmp_path / "approot"))
        paths = _reload_paths()
        assert paths.APP_ROOT == tmp_path / "approot"

    def test_settings_path_under_user_data(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STUDYBOT_USER_DATA", str(tmp_path / "ud"))
        monkeypatch.setenv("STUDYBOT_APP_ROOT", str(tmp_path / "ar"))
        paths = _reload_paths()
        assert paths.SETTINGS_PATH == tmp_path / "ud" / "config" / "settings.json"
        assert str(paths.SETTINGS_PATH).startswith(str(tmp_path / "ud"))

    def test_example_settings_under_app_root(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STUDYBOT_USER_DATA", str(tmp_path / "ud"))
        monkeypatch.setenv("STUDYBOT_APP_ROOT", str(tmp_path / "ar"))
        paths = _reload_paths()
        assert paths.EXAMPLE_SETTINGS_PATH == tmp_path / "ar" / "config" / "settings.example.json"
        assert str(paths.EXAMPLE_SETTINGS_PATH).startswith(str(tmp_path / "ar"))

    def test_chroma_db_dir_under_user_data(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STUDYBOT_USER_DATA", str(tmp_path / "ud"))
        monkeypatch.setenv("STUDYBOT_APP_ROOT", str(tmp_path / "ar"))
        paths = _reload_paths()
        assert paths.CHROMA_DB_DIR == tmp_path / "ud" / "data" / "chroma_db"

    def test_mastery_db_path_under_user_data(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STUDYBOT_USER_DATA", str(tmp_path / "ud"))
        monkeypatch.setenv("STUDYBOT_APP_ROOT", str(tmp_path / "ar"))
        paths = _reload_paths()
        assert paths.MASTERY_DB_PATH == tmp_path / "ud" / "data" / "mastery.db"

    def test_host_from_env(self, monkeypatch):
        monkeypatch.setenv("STUDYBOT_USER_DATA", "/tmp/ud")
        monkeypatch.setenv("STUDYBOT_APP_ROOT", "/tmp/ar")
        monkeypatch.setenv("STUDYBOT_HOST", "0.0.0.0")
        monkeypatch.setenv("STUDYBOT_PORT", "9999")
        paths = _reload_paths()
        assert paths.HOST == "0.0.0.0"
        assert paths.PORT == 9999

    def test_host_defaults(self, monkeypatch):
        monkeypatch.setenv("STUDYBOT_USER_DATA", "/tmp/ud")
        monkeypatch.setenv("STUDYBOT_APP_ROOT", "/tmp/ar")
        monkeypatch.delenv("STUDYBOT_HOST", raising=False)
        monkeypatch.delenv("STUDYBOT_PORT", raising=False)
        paths = _reload_paths()
        assert paths.HOST == "127.0.0.1"
        assert paths.PORT == 7777

    def test_logs_dir_under_user_data(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STUDYBOT_USER_DATA", str(tmp_path / "ud"))
        monkeypatch.setenv("STUDYBOT_APP_ROOT", str(tmp_path / "ar"))
        paths = _reload_paths()
        assert paths.LOGS_DIR == tmp_path / "ud" / "logs"

    def test_config_dir_under_user_data(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STUDYBOT_USER_DATA", str(tmp_path / "ud"))
        monkeypatch.setenv("STUDYBOT_APP_ROOT", str(tmp_path / "ar"))
        paths = _reload_paths()
        assert paths.CONFIG_DIR == tmp_path / "ud" / "config"


class TestDevMode:
    def test_project_root_fallback(self, monkeypatch):
        monkeypatch.delenv("STUDYBOT_USER_DATA", raising=False)
        monkeypatch.delenv("STUDYBOT_APP_ROOT", raising=False)
        paths = _reload_paths()
        assert paths.PROJECT_ROOT.exists()
        assert paths.USER_DATA_DIR == paths.PROJECT_ROOT
        assert paths.APP_ROOT == paths.PROJECT_ROOT

    def test_dev_paths_are_under_project_root(self, monkeypatch):
        monkeypatch.delenv("STUDYBOT_USER_DATA", raising=False)
        monkeypatch.delenv("STUDYBOT_APP_ROOT", raising=False)
        paths = _reload_paths()
        assert str(paths.SETTINGS_PATH).startswith(str(paths.PROJECT_ROOT))
        assert str(paths.CHROMA_DB_DIR).startswith(str(paths.PROJECT_ROOT))
        assert str(paths.MASTERY_DB_PATH).startswith(str(paths.PROJECT_ROOT))
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
PYTHONPATH=src/python python3 -m pytest tests/python/test_paths_packaging.py -v
```

Expected: FAIL — `paths` module does not export `USER_DATA_DIR`, `APP_ROOT`, `SETTINGS_PATH`, `EXAMPLE_SETTINGS_PATH`, `LOGS_DIR`, `CONFIG_DIR`, `HOST`, `PORT`.

- [ ] **Step 3: Implement the extended `paths.py`**

Replace `src/python/paths.py` with:

```python
import os
from pathlib import Path

_USER_DATA_ENV = os.environ.get("STUDYBOT_USER_DATA")
_APP_ROOT_ENV = os.environ.get("STUDYBOT_APP_ROOT")

if _USER_DATA_ENV and _APP_ROOT_ENV:
    USER_DATA_DIR = Path(_USER_DATA_ENV)
    APP_ROOT = Path(_APP_ROOT_ENV)
    PROJECT_ROOT = USER_DATA_DIR
else:
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    USER_DATA_DIR = PROJECT_ROOT
    APP_ROOT = PROJECT_ROOT

CONFIG_DIR = USER_DATA_DIR / "config"
DATA_DIR = USER_DATA_DIR / "data"
SETTINGS_PATH = CONFIG_DIR / "settings.json"
EXAMPLE_SETTINGS_PATH = APP_ROOT / "config" / "settings.example.json"
CHROMA_DB_DIR = DATA_DIR / "chroma_db"
MASTERY_DB_PATH = DATA_DIR / "mastery.db"
LOGS_DIR = USER_DATA_DIR / "logs"

HOST = os.environ.get("STUDYBOT_HOST", "127.0.0.1")
PORT = int(os.environ.get("STUDYBOT_PORT", "7777"))
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
PYTHONPATH=src/python python3 -m pytest tests/python/test_paths_packaging.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
PYTHONPATH=src/python python3 -m pytest tests/ -v
```

Expected: All existing tests still pass (env vars are absent, so dev-mode paths are used).

- [ ] **Step 6: Commit**

```bash
git add src/python/paths.py tests/python/test_paths_packaging.py
git commit -m "feat: extend paths.py with env-var-driven resolution for packaged mode"
```

---

## Task 2: Migrate `settings/router.py` to use `paths.py`

**Files:**
- Modify: `src/python/settings/router.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/python/test_paths_packaging.py`:

```python
class TestSettingsRouterUsesPaths:
    def test_settings_path_matches_paths_module(self, monkeypatch):
        monkeypatch.delenv("STUDYBOT_USER_DATA", raising=False)
        monkeypatch.delenv("STUDYBOT_APP_ROOT", raising=False)
        paths = _reload_paths()
        import importlib
        import settings.router as sr
        importlib.reload(sr)
        assert sr._SETTINGS_PATH == paths.SETTINGS_PATH

    def test_settings_path_packaged_mode(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STUDYBOT_USER_DATA", str(tmp_path / "ud"))
        monkeypatch.setenv("STUDYBOT_APP_ROOT", str(tmp_path / "ar"))
        paths = _reload_paths()
        import importlib
        import settings.router as sr
        importlib.reload(sr)
        assert sr._SETTINGS_PATH == tmp_path / "ud" / "config" / "settings.json"
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
PYTHONPATH=src/python python3 -m pytest tests/python/test_paths_packaging.py::TestSettingsRouterUsesPaths -v
```

Expected: FAIL — `_SETTINGS_PATH` in `settings/router.py` still uses its own `_PROJECT_ROOT`.

- [ ] **Step 3: Update `settings/router.py`**

In `src/python/settings/router.py`, remove these lines:

```python
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_SETTINGS_PATH = _PROJECT_ROOT / "config/settings.json"
```

Replace with:

```python
from paths import SETTINGS_PATH as _SETTINGS_PATH
```

Also remove the unused `from pathlib import Path` import if no other code in the file uses `Path` directly. Check: the file uses `Path` in `_run_pipeline_ingest_in_background` via `Path(__file__).resolve().parent.parent`. Update that function to not depend on `Path` for `cwd`. Change:

```python
cwd=str(Path(__file__).resolve().parent.parent),
```

to:

```python
cwd=str(Path(__file__).resolve().parent.parent),
```

This keeps `from pathlib import Path` in use. No change needed for that line.

- [ ] **Step 4: Run the test to verify it passes**

```bash
PYTHONPATH=src/python python3 -m pytest tests/python/test_paths_packaging.py::TestSettingsRouterUsesPaths -v
```

Expected: PASS.

- [ ] **Step 5: Run full test suite**

```bash
PYTHONPATH=src/python python3 -m pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/python/settings/router.py tests/python/test_paths_packaging.py
git commit -m "refactor: migrate settings/router.py to use paths module"
```

---

## Task 3: Migrate `llm/factory.py` to use `paths.py`

**Files:**
- Modify: `src/python/llm/factory.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/python/test_paths_packaging.py`:

```python
class TestFactoryUsesPaths:
    def test_default_config_path_matches_paths_module(self, monkeypatch):
        monkeypatch.delenv("STUDYBOT_USER_DATA", raising=False)
        monkeypatch.delenv("STUDYBOT_APP_ROOT", raising=False)
        paths = _reload_paths()
        import importlib
        import llm.factory as fac
        importlib.reload(fac)
        assert fac._DEFAULT_CONFIG_PATH == paths.SETTINGS_PATH

    def test_example_config_path_matches_paths_module(self, monkeypatch):
        monkeypatch.delenv("STUDYBOT_USER_DATA", raising=False)
        monkeypatch.delenv("STUDYBOT_APP_ROOT", raising=False)
        paths = _reload_paths()
        import importlib
        import llm.factory as fac
        importlib.reload(fac)
        assert fac._EXAMPLE_CONFIG_PATH == paths.EXAMPLE_SETTINGS_PATH
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
PYTHONPATH=src/python python3 -m pytest tests/python/test_paths_packaging.py::TestFactoryUsesPaths -v
```

Expected: FAIL.

- [ ] **Step 3: Update `llm/factory.py`**

In `src/python/llm/factory.py`, remove these lines:

```python
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_CONFIG_PATH = _PROJECT_ROOT / "config/settings.json"
_EXAMPLE_CONFIG_PATH = _PROJECT_ROOT / "config/settings.example.json"
```

Replace with:

```python
from paths import SETTINGS_PATH as _DEFAULT_CONFIG_PATH
from paths import EXAMPLE_SETTINGS_PATH as _EXAMPLE_CONFIG_PATH
```

Remove `from pathlib import Path` if no longer used. Check: `load_config` uses `Path(path)` — keep `from pathlib import Path`.

- [ ] **Step 4: Run the test to verify it passes**

```bash
PYTHONPATH=src/python python3 -m pytest tests/python/test_paths_packaging.py::TestFactoryUsesPaths -v
```

Expected: PASS.

- [ ] **Step 5: Run full test suite**

```bash
PYTHONPATH=src/python python3 -m pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/python/llm/factory.py tests/python/test_paths_packaging.py
git commit -m "refactor: migrate llm/factory.py to use paths module"
```

---

## Task 4: Migrate `llm/models.py` to use `paths.py`

**Files:**
- Modify: `src/python/llm/models.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/python/test_paths_packaging.py`:

```python
class TestModelsUsesPaths:
    def test_env_path_under_project_root(self, monkeypatch):
        monkeypatch.delenv("STUDYBOT_USER_DATA", raising=False)
        monkeypatch.delenv("STUDYBOT_APP_ROOT", raising=False)
        paths = _reload_paths()
        import importlib
        import llm.models as mod
        importlib.reload(mod)
        assert str(mod._ENV_PATH).startswith(str(paths.PROJECT_ROOT))
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
PYTHONPATH=src/python python3 -m pytest tests/python/test_paths_packaging.py::TestModelsUsesPaths -v
```

Expected: May pass or fail depending on whether the current `parents` count matches. The current code uses `parents[4]` via `parent.parent.parent.parent` which may or may not match `paths.py`'s `parents[2]`. The test verifies consistency.

- [ ] **Step 3: Update `llm/models.py`**

In `src/python/llm/models.py`, remove:

```python
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_ENV_PATH = _PROJECT_ROOT / ".env"
_ENV_EXAMPLE_PATH = _PROJECT_ROOT / ".env.example"
```

Replace with:

```python
from paths import PROJECT_ROOT

_ENV_PATH = PROJECT_ROOT / ".env"
_ENV_EXAMPLE_PATH = PROJECT_ROOT / ".env.example"
```

Note: `models.py` uses `Path` for other operations (`_ENV_PATH.read_text()`, etc.) so keep the `from pathlib import Path` import.

- [ ] **Step 4: Run the test to verify it passes**

```bash
PYTHONPATH=src/python python3 -m pytest tests/python/test_paths_packaging.py::TestModelsUsesPaths -v
```

Expected: PASS.

- [ ] **Step 5: Run full test suite**

```bash
PYTHONPATH=src/python python3 -m pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/python/llm/models.py tests/python/test_paths_packaging.py
git commit -m "refactor: migrate llm/models.py to use paths module"
```

---

## Task 5: Migrate `pipeline/run.py` to use `paths.py`

**Files:**
- Modify: `src/python/pipeline/run.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/python/test_paths_packaging.py`:

```python
class TestPipelineRunUsesPaths:
    def test_defaults_match_paths_module(self, monkeypatch):
        monkeypatch.delenv("STUDYBOT_USER_DATA", raising=False)
        monkeypatch.delenv("STUDYBOT_APP_ROOT", raising=False)
        paths = _reload_paths()
        import importlib
        import pipeline.run as pr
        importlib.reload(pr)
        assert pr.DEFAULT_DB_PATH == paths.CHROMA_DB_DIR
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
PYTHONPATH=src/python python3 -m pytest tests/python/test_paths_packaging.py::TestPipelineRunUsesPaths -v
```

Expected: Should already pass since `pipeline/run.py` imports `CHROMA_DB_DIR` from `paths`. But the `PROJECT_ROOT` and `DEFAULT_SOURCE_DIR` / `DEFAULT_RAW_DIR` / `DEFAULT_CLEANED_DIR` are computed independently. The test verifies `DEFAULT_DB_PATH` consistency.

If this test already passes, proceed anyway — the goal is to remove the redundant `PROJECT_ROOT` computation.

- [ ] **Step 3: Update `pipeline/run.py`**

In `src/python/pipeline/run.py`, remove:

```python
from paths import CHROMA_DB_DIR

# Resolve project root (StudyBot/)
PROJECT_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_SOURCE_DIR = PROJECT_ROOT / "docs" / "notabilityNotes" / "noteDocs"
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "notes_md" / "raw"
DEFAULT_CLEANED_DIR = PROJECT_ROOT / "data" / "notes_md" / "cleaned"
DEFAULT_DB_PATH = CHROMA_DB_DIR
```

Replace with:

```python
from paths import APP_ROOT, CHROMA_DB_DIR, DATA_DIR

DEFAULT_SOURCE_DIR = APP_ROOT / "docs" / "notabilityNotes" / "noteDocs"
DEFAULT_RAW_DIR = DATA_DIR / "notes_md" / "raw"
DEFAULT_CLEANED_DIR = DATA_DIR / "notes_md" / "cleaned"
DEFAULT_DB_PATH = CHROMA_DB_DIR
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
PYTHONPATH=src/python python3 -m pytest tests/python/test_paths_packaging.py::TestPipelineRunUsesPaths -v
```

Expected: PASS.

- [ ] **Step 5: Run full test suite**

```bash
PYTHONPATH=src/python python3 -m pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/python/pipeline/run.py tests/python/test_paths_packaging.py
git commit -m "refactor: migrate pipeline/run.py to use paths module"
```

---

## Task 6: Migrate `pipeline/personal_docs/run.py` to use `paths.py`

**Files:**
- Modify: `src/python/pipeline/personal_docs/run.py`

- [ ] **Step 1: Update `pipeline/personal_docs/run.py`**

In `src/python/pipeline/personal_docs/run.py`, remove:

```python
from paths import CHROMA_DB_DIR

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SOURCE_ROOT = PROJECT_ROOT / "docs"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "personal_docs" / "structured"
DEFAULT_DB_PATH = CHROMA_DB_DIR
```

Replace with:

```python
from paths import APP_ROOT, CHROMA_DB_DIR, DATA_DIR

DEFAULT_SOURCE_ROOT = APP_ROOT / "docs"
DEFAULT_OUTPUT_DIR = DATA_DIR / "personal_docs" / "structured"
DEFAULT_DB_PATH = CHROMA_DB_DIR
```

No new test needed — the existing `tests/pipeline/test_personal_docs*.py` and `test_run.py` cover these paths via CLI flag overrides and direct invocation.

- [ ] **Step 2: Run full test suite**

```bash
PYTHONPATH=src/python python3 -m pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 3: Commit**

```bash
git add src/python/pipeline/personal_docs/run.py
git commit -m "refactor: migrate pipeline/personal_docs/run.py to use paths module"
```

---

## Task 7: Update `main.py` — host/port and CORS

**Files:**
- Modify: `src/python/main.py`

- [ ] **Step 1: Write the failing test for CORS allowing file:// origins in packaged mode**

Add to `tests/python/test_paths_packaging.py`:

```python
class TestMainCors:
    def test_cors_allows_file_origin_in_packaged_mode(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STUDYBOT_USER_DATA", str(tmp_path / "ud"))
        monkeypatch.setenv("STUDYBOT_APP_ROOT", str(tmp_path / "ar"))
        import importlib
        import main
        importlib.reload(main)
        origins = [o for o in main.app.middleware_stack.__dict__.get("_user_middleware", [])]
        from fastapi.testclient import TestClient
        client = TestClient(main.app)
        response = client.options(
            "/health",
            headers={
                "Origin": "file:///path/to/index.html",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code in (200, 204)
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
PYTHONPATH=src/python python3 -m pytest tests/python/test_paths_packaging.py::TestMainCors -v
```

Expected: FAIL — CORS only allows `localhost:5173` and `localhost:5174`.

- [ ] **Step 3: Update `main.py`**

In `src/python/main.py`, update the CORS middleware and the `__main__` block.

Replace the CORS middleware configuration:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

With:

```python
from paths import HOST as _HOST, PORT as _PORT

_ALLOW_ORIGINS = ["http://localhost:5173", "http://localhost:5174"]
if os.environ.get("STUDYBOT_USER_DATA"):
    _ALLOW_ORIGINS.append("file://")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

And replace the `__main__` block:

```python
if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=7777, reload=False)
```

With:

```python
if __name__ == "__main__":
    uvicorn.run("main:app", host=_HOST, port=_PORT, reload=False)
```

Add the `paths` import at the top of the file alongside the other local imports:

```python
from paths import HOST as _HOST, PORT as _PORT
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
PYTHONPATH=src/python python3 -m pytest tests/python/test_paths_packaging.py::TestMainCors -v
```

Expected: PASS.

- [ ] **Step 5: Run full test suite**

```bash
PYTHONPATH=src/python python3 -m pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/python/main.py tests/python/test_paths_packaging.py
git commit -m "feat: use paths module for host/port and add file:// CORS in packaged mode"
```

---

## Task 8: Update Electron main process — `getBackendCommand()`

**Files:**
- Modify: `src/electron/main.js`

- [ ] **Step 1: Add `getBackendCommand()` helper**

Add this function in `src/electron/main.js` before the `startPython` function:

```javascript
function getBackendCommand() {
  if (isDev) {
    const scriptPath = path.join(app.getAppPath(), "src/python/main.py");
    return {
      executable: "python3",
      args: [scriptPath],
      cwd: app.getAppPath(),
      env: {
        ...process.env,
        PYTHONPATH: path.dirname(scriptPath),
      },
    };
  }

  const resourcesPath = process.resourcesPath;
  const isWin = process.platform === "win32";
  const pythonExe = isWin
    ? path.join(resourcesPath, "backend", "python.exe")
    : path.join(resourcesPath, "backend", "bin", "python");
  const backendEntry = path.join(
    resourcesPath,
    "backend",
    "app",
    "src",
    "python",
    "main.py"
  );

  return {
    executable: pythonExe,
    args: [backendEntry],
    cwd: path.join(resourcesPath, "backend"),
    env: {
      ...process.env,
      STUDYBOT_USER_DATA: app.getPath("userData"),
      STUDYBOT_APP_ROOT: resourcesPath,
      STUDYBOT_HOST: "127.0.0.1",
      STUDYBOT_PORT: "7777",
      PYTHONPATH: path.join(resourcesPath, "backend", "app", "src", "python"),
    },
  };
}
```

- [ ] **Step 2: Replace `startPython` to use `getBackendCommand()`**

Replace the existing `startPython` function:

```javascript
function startPython(launchId) {
  const scriptPath = isDev
    ? path.join(app.getAppPath(), "src/python/main.py")
    : path.join(process.resourcesPath, "src/python/main.py");

  const pythonDir = path.dirname(scriptPath);

  pythonProcess = spawn("python3", [scriptPath], {
    cwd: app.getAppPath(),
    env: {
      ...process.env,
      PYTHONPATH: pythonDir,
    },
  });
```

With:

```javascript
function startPython(launchId) {
  const cmd = getBackendCommand();

  pythonProcess = spawn(cmd.executable, cmd.args, {
    cwd: cmd.cwd,
    env: cmd.env,
  });
```

Also update the `appendBackendEvent` call after spawn to reference `cmd`:

```javascript
  appendBackendEvent("spawn", {
    message: "Python backend spawned",
    pid: pythonProcess.pid ?? null,
    scriptPath: cmd.args[0],
  });
```

- [ ] **Step 3: Run frontend tests**

```bash
npx vitest run
```

Expected: All frontend tests pass.

- [ ] **Step 4: Commit**

```bash
git add src/electron/main.js
git commit -m "feat: add getBackendCommand() for bundled Python in packaged mode"
```

---

## Task 9: Create macOS backend payload build script

**Files:**
- Create: `scripts/package-backend.sh`

- [ ] **Step 1: Create the script**

Create `scripts/package-backend.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 <arch> [python-version]"
  echo "  arch:           arm64 | x64"
  echo "  python-version: e.g. 3.12.3 (default: 3.12.3)"
  exit 1
}

ARCH="${1:-}"
PYTHON_VERSION="${2:-3.12.3}"

if [[ "$ARCH" != "arm64" && "$ARCH" != "x64" ]]; then
  usage
fi

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="$REPO_ROOT/build/resources/backend"
STAGING_DIR="$BUILD_DIR/staging"

echo "=== Packaging backend for macOS $ARCH, Python $PYTHON_VERSION ==="

rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR"

PYTHON_BIN_DIR="$STAGING_DIR/bin"
PYTHON_LIB_DIR="$STAGING_DIR/lib"
APP_DIR="$STAGING_DIR/app"

mkdir -p "$PYTHON_BIN_DIR" "$PYTHON_LIB_DIR" "$APP_DIR"

echo "--- Copying backend source ---"
cp -R "$REPO_ROOT/src/python" "$APP_DIR/src/python"

echo "--- Creating venv and installing dependencies ---"
UV="$(command -v uv || true)"
if [[ -n "$UV" ]]; then
  echo "Using uv for dependency installation"
  "$UV" venv "$STAGING_DIR/venv" --python "$PYTHON_VERSION"
  source "$STAGING_DIR/venv/bin/activate"
  if [[ -f "$REPO_ROOT/requirements.txt" ]]; then
    "$UV" pip install -r "$REPO_ROOT/requirements.txt" --target "$PYTHON_LIB_DIR"
  fi
  deactivate
else
  echo "Using pip for dependency installation"
  PYTHON="python3"
  if ! command -v "$PYTHON" &>/dev/null; then
    echo "ERROR: python3 not found on PATH"
    exit 1
  fi
  "$PYTHON" -m venv "$STAGING_DIR/venv"
  source "$STAGING_DIR/venv/bin/activate"
  if [[ -f "$REPO_ROOT/requirements.txt" ]]; then
    pip install -r "$REPO_ROOT/requirements.txt" --target "$PYTHON_LIB_DIR"
  fi
  deactivate
fi

cp "$STAGING_DIR/venv/bin/python" "$PYTHON_BIN_DIR/python" 2>/dev/null || true
cp "$STAGING_DIR/venv/bin/python3" "$PYTHON_BIN_DIR/python3" 2>/dev/null || true

echo "--- Validating staged runtime ---"
STAGED_PYTHON="$PYTHON_BIN_DIR/python3"
if [[ ! -x "$STAGED_PYTHON" ]]; then
  STAGED_PYTHON="$PYTHON_BIN_DIR/python"
fi
if [[ ! -x "$STAGED_PYTHON" ]]; then
  STAGED_PYTHON="$STAGING_DIR/venv/bin/python3"
fi

PYTHONPATH="$PYTHON_LIB_DIR:$APP_DIR/src/python" "$STAGED_PYTHON" -c "
import fastapi
import uvicorn
import chromadb
print(f'fastapi {fastapi.__version__}')
print(f'uvicorn {uvicorn.__version__}')
print(f'chromadb {chromadb.__version__}')
print('All required imports OK')
"

echo "--- Finalising payload ---"
rm -rf "$STAGING_DIR/venv"
OUTPUT_DIR="$REPO_ROOT/build/resources/backend-mac-$ARCH"
rm -rf "$OUTPUT_DIR"
mv "$STAGING_DIR" "$OUTPUT_DIR"
rmdir "$BUILD_DIR" 2>/dev/null || true

echo "=== Backend payload at $OUTPUT_DIR ==="
ls -la "$OUTPUT_DIR"
echo "=== Done ==="
```

- [ ] **Step 2: Make the script executable**

```bash
chmod +x scripts/package-backend.sh
```

- [ ] **Step 3: Commit**

```bash
git add scripts/package-backend.sh
git commit -m "feat: add macOS backend payload build script"
```

---

## Task 10: Create Windows backend payload build script

**Files:**
- Create: `scripts/package-backend.ps1`

- [ ] **Step 1: Create the script**

Create `scripts/package-backend.ps1`:

```powershell
<#
.SYNOPSIS
    Packages the Python backend for Windows x64 standalone builds.
.PARAMETER PythonVersion
    Python version to use (default: 3.12.3)
#>
param(
    [string]$PythonVersion = "3.12.3"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$BuildDir = Join-Path $RepoRoot "build\resources\backend"
$StagingDir = Join-Path $BuildDir "staging"

Write-Host "=== Packaging backend for Windows x64, Python $PythonVersion ==="

if (Test-Path $StagingDir) { Remove-Item -Recurse -Force $StagingDir }
New-Item -ItemType Directory -Force -Path $StagingDir | Out-Null

$PythonDir = Join-Path $StagingDir "python"
$LibDir = Join-Path $StagingDir "Lib"
$AppDir = Join-Path $StagingDir "app"

New-Item -ItemType Directory -Force -Path $PythonDir | Out-Null
New-Item -ItemType Directory -Force -Path $LibDir | Out-Null
New-Item -ItemType Directory -Force -Path $AppDir | Out-Null

Write-Host "--- Copying backend source ---"
Copy-Item -Recurse -Path (Join-Path $RepoRoot "src\python") -Destination (Join-Path $AppDir "src\python")

Write-Host "--- Installing dependencies ---"
$VenvDir = Join-Path $StagingDir "venv"
& python -m venv $VenvDir
$PipExe = Join-Path $VenvDir "Scripts\pip.exe"
$PythonExe = Join-Path $VenvDir "Scripts\python.exe"

$RequirementsFile = Join-Path $RepoRoot "requirements.txt"
if (Test-Path $RequirementsFile) {
    & $PipExe install -r $RequirementsFile --target $LibDir
}

Copy-Item -Path (Join-Path $VenvDir "Scripts\python.exe") -Destination (Join-Path $PythonDir "python.exe") -ErrorAction SilentlyContinue
Copy-Item -Path (Join-Path $VenvDir "Scripts\python3.exe") -Destination (Join-Path $PythonDir "python3.exe") -ErrorAction SilentlyContinue
Copy-Item -Path (Join-Path $VenvDir "Scripts\pythonw.exe") -Destination (Join-Path $PythonDir "pythonw.exe") -ErrorAction SilentlyContinue

$VenvLibPython = Get-ChildItem -Path (Join-Path $VenvDir "Lib") -Directory -Filter "python*" | Select-Object -First 1
if ($VenvLibPython) {
    $ZippedPyc = Join-Path $VenvLibPython.FullName "python.zip"
    if (Test-Path $ZippedPyc) {
        Copy-Item -Path $ZippedPyc -Destination $PythonDir
    }
}

Write-Host "--- Validating staged runtime ---"
$env:PYTHONPATH = "$LibDir;$AppDir\src\python"
& $PythonExe -c @"
import fastapi
import uvicorn
import chromadb
print(f'fastapi {fastapi.__version__}')
print(f'uvicorn {uvicorn.__version__}')
print(f'chromadb {chromadb.__version__}')
print('All required imports OK')
"@

Write-Host "--- Finalising payload ---"
Remove-Item -Recurse -Force $VenvDir

$OutputDir = Join-Path $RepoRoot "build\resources\backend-win-x64"
if (Test-Path $OutputDir) { Remove-Item -Recurse -Force $OutputDir }
Move-Item -Path $StagingDir -Destination $OutputDir
if (Test-Path $BuildDir) { Remove-Item -Recurse -Force $BuildDir -ErrorAction SilentlyContinue }

Write-Host "=== Backend payload at $OutputDir ==="
Get-ChildItem $OutputDir
Write-Host "=== Done ==="
```

- [ ] **Step 2: Commit**

```bash
git add scripts/package-backend.ps1
git commit -m "feat: add Windows backend payload build script"
```

---

## Task 11: Add first-run seeding in Python

**Files:**
- Create: `src/python/seed.py`
- Modify: `src/python/main.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/python/test_paths_packaging.py`:

```python
import shutil


class TestFirstRunSeeding:
    def test_seeds_settings_from_example(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STUDYBOT_USER_DATA", str(tmp_path / "ud"))
        monkeypatch.setenv("STUDYBOT_APP_ROOT", str(tmp_path / "ar"))
        paths = _reload_paths()

        example_dir = tmp_path / "ar" / "config"
        example_dir.mkdir(parents=True)
        (example_dir / "settings.example.json").write_text('{"test": true}')

        import importlib
        import seed
        importlib.reload(seed)
        seed.seed_user_data()

        settings = (tmp_path / "ud" / "config" / "settings.json").read_text()
        assert '"test"' in settings

    def test_does_not_overwrite_existing_settings(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STUDYBOT_USER_DATA", str(tmp_path / "ud"))
        monkeypatch.setenv("STUDYBOT_APP_ROOT", str(tmp_path / "ar"))
        paths = _reload_paths()

        config_dir = tmp_path / "ud" / "config"
        config_dir.mkdir(parents=True)
        (config_dir / "settings.json").write_text('{"existing": true}')

        example_dir = tmp_path / "ar" / "config"
        example_dir.mkdir(parents=True)
        (example_dir / "settings.example.json").write_text('{"test": true}')

        import importlib
        import seed
        importlib.reload(seed)
        seed.seed_user_data()

        settings = (config_dir / "settings.json").read_text()
        assert '"existing"' in settings
        assert '"test"' not in settings

    def test_creates_writable_dirs(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STUDYBOT_USER_DATA", str(tmp_path / "ud"))
        monkeypatch.setenv("STUDYBOT_APP_ROOT", str(tmp_path / "ar"))
        paths = _reload_paths()

        import importlib
        import seed
        importlib.reload(seed)
        seed.seed_user_data()

        assert (tmp_path / "ud" / "data" / "chroma_db").is_dir()
        assert (tmp_path / "ud" / "logs").is_dir()
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
PYTHONPATH=src/python python3 -m pytest tests/python/test_paths_packaging.py::TestFirstRunSeeding -v
```

Expected: FAIL — `seed` module does not exist.

- [ ] **Step 3: Create `src/python/seed.py`**

```python
import json
import shutil
from pathlib import Path

from paths import (
    CHROMA_DB_DIR,
    CONFIG_DIR,
    EXAMPLE_SETTINGS_PATH,
    LOGS_DIR,
    SETTINGS_PATH,
)


def seed_user_data() -> None:
    _ensure_settings()
    _ensure_dirs()


def _ensure_settings() -> None:
    if SETTINGS_PATH.exists():
        return
    if not EXAMPLE_SETTINGS_PATH.exists():
        return
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(EXAMPLE_SETTINGS_PATH, SETTINGS_PATH)


def _ensure_dirs() -> None:
    CHROMA_DB_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
PYTHONPATH=src/python python3 -m pytest tests/python/test_paths_packaging.py::TestFirstRunSeeding -v
```

Expected: PASS.

- [ ] **Step 5: Wire seeding into `main.py`**

In `src/python/main.py`, add the import and call in the lifespan:

```python
from seed import seed_user_data
```

In the `lifespan` function, add the seeding call before `_start_warmup_thread()`:

```python
@asynccontextmanager
async def lifespan(_: FastAPI):
    seed_user_data()
    _start_warmup_thread()
    yield
```

- [ ] **Step 6: Run full test suite**

```bash
PYTHONPATH=src/python python3 -m pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/python/seed.py src/python/main.py tests/python/test_paths_packaging.py
git commit -m "feat: add first-run seeding for settings and writable directories"
```

---

## Task 12: Create electron-builder configuration

**Files:**
- Create: `electron-builder.yml`
- Modify: `package.json`

- [ ] **Step 1: Create `electron-builder.yml`**

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

- [ ] **Step 2: Remove inline `build` config from `package.json`**

In `package.json`, remove the entire `"build"` key:

```json
  "build": {
    "appId": "com.studybot.clinical-recall",
    "productName": "Clinical Recall Assistant",
    "mac": {
      "category": "public.app-category.education"
    },
    "files": [
      "dist/**/*",
      "src/electron/**/*",
      "src/python/**/*"
    ]
  }
```

This is replaced by `electron-builder.yml`.

- [ ] **Step 3: Run frontend tests**

```bash
npx vitest run
```

Expected: All tests pass.

- [ ] **Step 4: Commit**

```bash
git add electron-builder.yml package.json
git commit -m "feat: add electron-builder.yml config for macOS and Windows builds"
```

---

## Task 13: Update the packaging playbook

**Files:**
- Modify: `Guides/standalone-packaging-macos-windows.md`

- [ ] **Step 1: Update the status tracker**

In `Guides/standalone-packaging-macos-windows.md`, update the step checkboxes for Phases A-E to reflect the completed work:

Under Phase A, mark steps A1-A6 as `[x]`.
Under Phase B, mark steps B1-B6 as `[x]`.
Under Phase C, mark steps C1-C5 as `[x]`.
Under Phase D, mark steps D1-D5 as `[x]`.
Under Phase E, mark steps E1-E8 as `[x]`.

- [ ] **Step 2: Add a build note**

In the Build Notes section, add:

```markdown
### 2026-04-05 — Phases A-E implementation

- Phase A: Unified path resolution via `paths.py` with env-var-driven mode. All consumer modules migrated. Tests in `tests/python/test_paths_packaging.py`.
- Phase B: `getBackendCommand()` added to Electron main process. Dev mode unchanged. Production mode uses bundled Python with env vars.
- Phase C: `scripts/package-backend.sh` (macOS) and `scripts/package-backend.ps1` (Windows) created.
- Phase D: `src/python/seed.py` handles first-run seeding of settings and writable directories.
- Phase E: `electron-builder.yml` created with macOS dmg and Windows nsis targets. Inline build config removed from `package.json`.
```

- [ ] **Step 3: Commit**

```bash
git add Guides/standalone-packaging-macos-windows.md
git commit -m "docs: update packaging playbook with Phases A-E completion"
```

---

## Task 14: Final verification

**Files:**
- None (verification only)

- [ ] **Step 1: Run all Python tests**

```bash
PYTHONPATH=src/python python3 -m pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 2: Run all frontend tests**

```bash
npx vitest run
```

Expected: All tests pass.

- [ ] **Step 3: Run TypeScript typecheck**

```bash
npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 4: Verify dev mode still works**

```bash
PYTHONPATH=src/python python3 -c "from paths import PROJECT_ROOT; print(PROJECT_ROOT)"
```

Expected: Prints the worktree repo root path.

- [ ] **Step 5: Verify packaged-mode paths work**

```bash
STUDYBOT_USER_DATA=/tmp/test-ud STUDYBOT_APP_ROOT=/tmp/test-ar PYTHONPATH=src/python python3 -c "from paths import USER_DATA_DIR, APP_ROOT, SETTINGS_PATH; print(USER_DATA_DIR, APP_ROOT, SETTINGS_PATH)"
```

Expected: `/tmp/test-ud /tmp/test-ar /tmp/test-ud/config/settings.json`

- [ ] **Step 6: Final commit if any fixes were needed**

Only if changes were required:

```bash
git add -A && git commit -m "fix: address regressions found during final verification"
```
