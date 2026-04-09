# Phase 0: Project Setup and Scaffolding — Design Spec

**Date:** 2026-04-01
**Project:** Clinical Recall Assistant (StudyBot)
**Phase:** 0 — Project Setup and Scaffolding

---

## Overview

Phase 0 establishes the foundational project skeleton: git repository, confirmed technology stack, directory structure, and minimal stub files for each layer of the application. No business logic is implemented — the goal is a running Electron window backed by a live Python server, confirming all tooling is wired correctly.

---

## Technology Stack (Confirmed)

| Concern | Choice | Rationale |
|---------|--------|-----------|
| GUI Framework | Electron + React | Mature ecosystem, fastest path to the editorial design system |
| Bundler | Vite | Fast HMR, native ESM, standard for React |
| Styling | Tailwind CSS | Already used in Stitch prototypes |
| Python ↔ Electron bridge | FastAPI (local HTTP, port 7777) | Debuggable, supports SSE for streaming LLM output |
| Vector DB | ChromaDB | Already specified in pipeline guides, local |
| LLM integration | Multi-provider abstraction (Phase 4) | Anthropic, Google, Z.ai |
| State / quiz history | SQLite (Phase 4) | Lightweight, local |
| Data pipeline | Python scripts (Phase 1–3) | Already specified |

---

## Directory Structure

```
StudyBot/
├── index.html                 # Vite entry point — mounts <div id="root">, loads src/renderer/main.tsx
├── src/
│   ├── electron/
│   │   ├── main.js            # Main process: BrowserWindow, spawns Python, kills on quit
│   │   └── preload.js         # contextBridge: exposes window.api to renderer
│   ├── renderer/              # React app (Vite-bundled)
│   │   ├── components/        # Reusable UI components
│   │   ├── pages/             # Screen-level components
│   │   ├── hooks/             # React hooks
│   │   ├── App.tsx            # Root component — health-check placeholder
│   │   └── main.tsx           # React entry point: mounts <App /> to #root
│   └── python/
│       ├── main.py            # FastAPI app on 127.0.0.1:7777, GET /health
│       ├── pipeline/          # (empty — Phase 1+)
│       ├── quiz/              # (empty — Phase 4+)
│       └── llm/               # (empty — Phase 4+)
├── data/
│   ├── cmgs/                  # Extracted CMG JSON (Phase 2)
│   ├── notes_md/              # Cleaned notability markdown (Phase 1)
│   └── chroma_db/             # ChromaDB persistent store (Phase 1+)
├── config/
│   └── settings.json          # Default model/provider config (gitignored — contains API keys)
├── dist/                      # Vite production output (gitignored)
├── build/                     # electron-builder output (gitignored)
├── docs/                      # Existing project docs (unchanged)
├── package.json               # Electron + React + Vite + Tailwind + electron-builder + concurrently
├── pyproject.toml             # Python deps: fastapi, uvicorn, chromadb, langchain-text-splitters, playwright, pydantic
├── vite.config.ts             # Renderer Vite config (root at project root, output to dist/)
├── tailwind.config.js         # Font config: Newsreader, Space Grotesk, IBM Plex Mono
└── tsconfig.json              # Standard Vite + React defaults
```

---

## Key File Responsibilities

### `index.html`
Standard Vite HTML entry point at project root:
```html
<div id="root"></div>
<script type="module" src="/src/renderer/main.tsx"></script>
```

### `src/electron/main.js`
- On `app.whenReady()`:
  - Resolves Python script path dynamically:
    - Dev: `path.join(app.getAppPath(), 'src/python/main.py')`
    - Prod: `path.join(process.resourcesPath, 'src/python/main.py')`
    - Distinguishes dev/prod via `process.env.NODE_ENV === 'development'`
  - Spawns Python via `child_process.spawn('python3', [pythonScriptPath])`
  - Pipes Python stdout/stderr to console for debugging
  - Creates a `BrowserWindow` loading:
    - **Dev:** `http://localhost:5173` (Vite dev server)
    - **Prod:** `file://${path.join(app.getAppPath(), 'dist/index.html')}`
- On `app.on('quit')`: kills the Python child process
- `package.json` must include `"main": "src/electron/main.js"` for Electron to find the entry point

### `src/electron/preload.js`
- Exposes `window.api` via `contextBridge.exposeInMainWorld`
- Placeholder only in Phase 0; IPC methods added in later phases

### `src/python/main.py`
- FastAPI app bound to `127.0.0.1:7777`
- CORS middleware allows `http://localhost:5173` and `http://localhost:*` for dev
- Note: In production (Electron `file://` protocol), the renderer does not send an `Origin` header, so CORS does not apply — the server is accessible from any local caller
- Single route: `GET /health` → `{"status": "ok", "version": "0.1.0"}`
- Started with `uvicorn main:app --host 127.0.0.1 --port 7777`

### `src/renderer/main.tsx`
- React entry point: imports React, ReactDOM, and `App`
- Mounts `<App />` to `document.getElementById('root')`

### `src/renderer/App.tsx`
- On mount, calls `fetch("http://localhost:7777/health")`
- Displays: `"Backend connected"` if `/health` returns 200, `"Backend unavailable"` otherwise
- Placeholder for the Archival Protocol design system (implemented Phase 5)

### `vite.config.ts`
```ts
// Project root is StudyBot/; index.html is at root; output to dist/
export default defineConfig({
  plugins: [react()],
  base: './',
  // base: './' produces relative asset paths (e.g. ./assets/index.js).
  // Electron's file:// protocol resolves these relative to the loaded
  // index.html, so this works correctly in both dev and production.
  build: {
    outDir: 'dist',      // electron-builder picks up from dist/
  },
  server: {
    port: 5173,
  },
})
```

### `config/settings.json`
```json
{
  "provider": "anthropic",
  "quiz_model": "claude-haiku-4-5",
  "clean_model": "claude-opus-4-5",
  "api_key": ""
}
```
Gitignored (contains API keys). A `config/settings.example.json` with empty `api_key` is committed as reference.

### `.gitignore`
```
node_modules/
dist/
build/
.vite/
.cache/
__pycache__/
*.pyc
data/chroma_db/
config/settings.json
.env
.env.local
.env.*.local
.venv/
*.egg-info/
.DS_Store
*.log
npm-debug.log*
*.swp
*.swo
```

---

## NPM Scripts

| Script | Action |
|--------|--------|
| `dev` | `concurrently "vite" "electron ."` — runs Vite dev server + Electron in parallel |
| `build` | `vite build && electron-builder` — bundles React then packages app |
| `python:start` | `python3 src/python/main.py` — starts FastAPI standalone for backend dev |

Uses `concurrently` npm package for the `dev` script.

---

## Python Dependencies (`pyproject.toml`)

```toml
[build-system]
requires = ["setuptools", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "studybot-backend"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
  "fastapi",
  "uvicorn[standard]",
  "chromadb",
  "langchain-text-splitters",
  "playwright",
  "pydantic",
]
```

Install with: `pip install -e .` from the project root.

---

## electron-builder

Full packaging configuration deferred to a later phase. Phase 0 includes `electron-builder` in `devDependencies` only. A minimal `build` config in `package.json` is added to confirm the tool is wired, targeting macOS (current dev platform).

---

## Success Criteria for Phase 0

- [ ] `git init` complete with initial commit
- [ ] `npm install` succeeds with no errors
- [ ] `python3 -m pip install -e .` (or equivalent) succeeds
- [ ] `npm run dev` opens an Electron window
- [ ] Python FastAPI server starts automatically with Electron (visible in console logs)
- [ ] `GET http://localhost:7777/health` returns `{"status": "ok", "version": "0.1.0"}`
- [ ] React renderer displays `"Backend connected"` on launch
- [ ] React renderer displays `"Backend unavailable"` if Python is not running
- [ ] `InfoERRORS.md` exists (already complete)
- [ ] TODO.md updated to mark Phase 0 items complete
