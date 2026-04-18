# Windows PYTHONPATH Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix production PYTHONPATH on Windows so the packaged app can find pip-installed dependencies (fastapi, uvicorn, chromadb).

**Architecture:** The macOS packaging script installs pip packages directly into `backend/lib/`, but the Windows script installs them into `backend/Lib/site-packages/`. The Electron main process PYTHONPATH only includes `backend/lib`, which works on macOS but misses the Windows location. Add a Windows-specific `Lib/site-packages` entry to PYTHONPATH.

**Tech Stack:** Node.js (Electron main process), path module

---

### Task 1: Add Windows site-packages to PYTHONPATH

**Files:**
- Modify: `src/electron/main.js:128-131`

**Context:** The packaging scripts produce different layouts:

| Platform | stdlib | pip packages | Current PYTHONPATH |
|----------|--------|-------------|-------------------|
| macOS | `backend/lib/python3.12/` | `backend/lib/` (via `--target`) | `backend/lib` — works |
| Windows | `backend/Lib/` (copied) | `backend/Lib/site-packages/` (via `--target`) | `backend/lib` — broken, packages are in `Lib/site-packages` |

- [ ] **Step 1: Update PYTHONPATH construction in `getBackendCommand()`**

In `src/electron/main.js`, replace lines 128-131:

```js
// Before:
PYTHONPATH: [
  path.join(resourcesPath, "backend", "lib"),
  path.join(resourcesPath, "backend", "app", "src", "python"),
].join(isWin ? ";" : ":"),

// After:
PYTHONPATH: [
  path.join(resourcesPath, "backend", isWin ? "Lib" : "lib"),
  ...(isWin
    ? [path.join(resourcesPath, "backend", "Lib", "site-packages")]
    : []),
  path.join(resourcesPath, "backend", "app", "src", "python"),
].join(isWin ? ";" : ":"),
```

- [ ] **Step 2: Verify no other PYTHONPATH references in the codebase**

Run: `grep -n "PYTHONPATH" src/electron/main.js`

Expected: Only the one location in `getBackendCommand()` should appear (already verified — single occurrence).

- [ ] **Step 3: Commit**

```bash
git add src/electron/main.js
git commit -m "fix: add Windows Lib/site-packages to PYTHONPATH for packaged backend"
```
