# Phase 0: Project Setup and Scaffolding — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a running Electron window backed by a live FastAPI Python server, with all project tooling wired and confirmed working.

**Architecture:** Electron (main process) spawns a FastAPI server on 127.0.0.1:7777, then opens a BrowserWindow loading a Vite-bundled React app. React calls `/health` on mount and shows "Backend connected" or "Backend unavailable". All Python pipeline, quiz, and LLM modules are empty stubs for future phases.

**Tech Stack:** Electron 32, React 19, Vite 6, Tailwind CSS 3, TypeScript 5, FastAPI, uvicorn, pytest, vitest, @testing-library/react

---

> **Note:** This project has no existing git repo. Skip worktree setup — initialise git in Task 1.

---

## File Map

| File | Created/Modified | Responsibility |
|------|-----------------|----------------|
| `.gitignore` | Create | Exclude node_modules, dist, chroma_db, settings.json, pycache |
| `pyproject.toml` | Create | Python deps + dev test deps (pytest, httpx) |
| `package.json` | Create | Node deps, npm scripts, Electron entry point |
| `tsconfig.json` | Create | TypeScript config for Vite + React |
| `vite.config.ts` | Create | Vite config with React plugin, vitest config, base: './' |
| `tailwind.config.js` | Create | Tailwind v3 with custom font families |
| `index.html` | Create | Vite HTML entry point, mounts #root |
| `src/electron/main.js` | Create | Main process: spawn Python, open BrowserWindow, cleanup |
| `src/electron/preload.js` | Create | contextBridge stub exposing window.api |
| `src/python/main.py` | Create | FastAPI app on :7777, GET /health |
| `src/python/__init__.py` | Create | Empty package marker |
| `src/python/pipeline/__init__.py` | Create | Empty package marker |
| `src/python/quiz/__init__.py` | Create | Empty package marker |
| `src/python/llm/__init__.py` | Create | Empty package marker |
| `src/renderer/main.tsx` | Create | React entry point, mounts App to #root |
| `src/renderer/App.tsx` | Create | Health-check component |
| `src/renderer/styles/global.css` | Create | Tailwind directives |
| `config/settings.example.json` | Create | Committed reference config (no real keys) |
| `config/settings.json` | Create | Real config (gitignored) |
| `data/cmgs/.gitkeep` | Create | Preserve empty directory in git |
| `data/notes_md/.gitkeep` | Create | Preserve empty directory in git |
| `data/chroma_db/.gitkeep` | Create | Preserve empty directory (gitignored content) |
| `tests/python/__init__.py` | Create | Empty package marker |
| `tests/python/test_health.py` | Create | Pytest tests for /health endpoint |
| `tests/renderer/setup.ts` | Create | @testing-library/jest-dom import |
| `tests/renderer/App.test.tsx` | Create | Vitest tests for App health-check display |
| `TODO.md` | Modify | Mark Phase 0 items complete |

---

## Task 1: Initialise git repository

**Files:**
- Create: `.gitignore`

- [ ] **Step 1: Run git init**

```bash
cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot
git init
```

Expected output: `Initialized empty Git repository in .../StudyBot/.git/`

- [ ] **Step 2: Create .gitignore**

Create `.gitignore`:
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

- [ ] **Step 3: Commit existing project files**

```bash
git add .
git commit -m "chore: initialise repository with existing project docs and guides"
```

---

## Task 2: Python backend — write failing test

**Files:**
- Create: `pyproject.toml`
- Create: `tests/python/__init__.py`
- Create: `tests/python/test_health.py`

- [ ] **Step 1: Create pyproject.toml**

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

[project.optional-dependencies]
dev = [
  "pytest",
  "httpx",
]
```

- [ ] **Step 2: Install Python dependencies**

```bash
pip install -e ".[dev]"
```

Expected: all packages install without error.

- [ ] **Step 3: Create test directory and files**

Create `tests/python/__init__.py` (empty file).

Create `tests/python/test_health.py`:
```python
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src/python")))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health_returns_200():
    response = client.get("/health")
    assert response.status_code == 200


def test_health_response_shape():
    response = client.get("/health")
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"
```

- [ ] **Step 4: Run test — verify it fails**

```bash
pytest tests/python/test_health.py -v
```

Expected: `ModuleNotFoundError: No module named 'main'` or `ImportError`. The test must fail before we implement.

---

## Task 3: Python backend — implement and pass tests

**Files:**
- Create: `src/python/__init__.py`
- Create: `src/python/pipeline/__init__.py`
- Create: `src/python/quiz/__init__.py`
- Create: `src/python/llm/__init__.py`
- Create: `src/python/main.py`

- [ ] **Step 1: Create package markers**

Create these four empty files:
- `src/python/__init__.py`
- `src/python/pipeline/__init__.py`
- `src/python/quiz/__init__.py`
- `src/python/llm/__init__.py`

- [ ] **Step 2: Create FastAPI app**

Create `src/python/main.py`:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="StudyBot Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": "0.1.0"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=7777, reload=False)
```

- [ ] **Step 3: Run tests — verify they pass**

```bash
pytest tests/python/test_health.py -v
```

Expected output:
```
tests/python/test_health.py::test_health_returns_200 PASSED
tests/python/test_health.py::test_health_response_shape PASSED
2 passed in ...
```

- [ ] **Step 4: Commit**

```bash
git add src/python/ tests/python/ pyproject.toml
git commit -m "feat: add Python backend skeleton with FastAPI health endpoint"
```

---

## Task 4: Node project setup

**Files:**
- Create: `package.json`
- Create: `tsconfig.json`
- Create: `vite.config.ts`
- Create: `tailwind.config.js`

- [ ] **Step 1: Create package.json**

```json
{
  "name": "clinical-recall-assistant",
  "version": "0.1.0",
  "description": "ACTAS paramedic clinical study tool",
  "main": "src/electron/main.js",
  "homepage": "./",
  "scripts": {
    "dev": "concurrently -k \"vite\" \"wait-on http://localhost:5173 && NODE_ENV=development electron .\"",
    "build": "vite build && electron-builder",
    "test": "vitest run",
    "test:watch": "vitest",
    "python:start": "python3 src/python/main.py"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.0.0",
    "@testing-library/react": "^16.0.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@vitejs/plugin-react": "^4.0.0",
    "autoprefixer": "^10.0.0",
    "concurrently": "^9.0.0",
    "electron": "^32.0.0",
    "electron-builder": "^25.0.0",
    "jsdom": "^25.0.0",
    "postcss": "^8.0.0",
    "tailwindcss": "^3.4.0",
    "typescript": "^5.0.0",
    "vite": "^6.0.0",
    "vitest": "^2.0.0",
    "wait-on": "^8.0.0"
  },
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0"
  },
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
}
```

- [ ] **Step 2: Create tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src/renderer", "tests/renderer"]
}
```

- [ ] **Step 3: Create vite.config.ts**

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "./",
  // base: './' produces relative asset paths.
  // Electron's file:// protocol resolves these relative to index.html — correct in both dev and prod.
  build: {
    outDir: "dist",
  },
  server: {
    port: 5173,
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["tests/renderer/setup.ts"],
  },
});
```

- [ ] **Step 4: Create tailwind.config.js**

```js
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./index.html", "./src/renderer/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        serif: ["Newsreader", "Georgia", "serif"],
        sans: ["Space Grotesk", "system-ui", "sans-serif"],
        mono: ["IBM Plex Mono", "Menlo", "monospace"],
      },
      colors: {
        teal: {
          archival: "#2D5A54",
        },
        accent: {
          highlighter: "#DAE058",
        },
        surface: {
          base: "#FBF9F3",
        },
      },
    },
  },
  plugins: [],
};
```

- [ ] **Step 5: Install Node dependencies**

```bash
npm install
```

Expected: `node_modules/` created, no errors. (Warnings about peer deps are acceptable.)

---

## Task 5: React renderer — write failing tests

**Files:**
- Create: `tests/renderer/setup.ts`
- Create: `tests/renderer/App.test.tsx`

- [ ] **Step 1: Create test setup file**

Create `tests/renderer/setup.ts`:
```ts
import "@testing-library/jest-dom";
```

- [ ] **Step 2: Create failing App tests**

Create `tests/renderer/App.test.tsx`:
```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import App from "../../src/renderer/App";

describe("App", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('shows "Backend connected" when health check succeeds on first attempt', async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValue({ status: "ok", version: "0.1.0" }),
      })
    );

    render(<App />);
    await vi.runAllTimersAsync();

    expect(screen.getByText("Backend connected")).toBeInTheDocument();
  });

  it('shows "Backend unavailable" when all retry attempts fail', async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("Connection refused"))
    );

    render(<App />);
    // Advance through all retry delays (3 attempts × 800ms each)
    await vi.runAllTimersAsync();

    expect(screen.getByText("Backend unavailable")).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run tests — verify they fail**

```bash
npm test
```

Expected: `Cannot find module '../../src/renderer/App'`. Tests must fail before implementation.

---

## Task 6: React renderer — implement and pass tests

**Files:**
- Create: `index.html`
- Create: `src/renderer/main.tsx`
- Create: `src/renderer/App.tsx`
- Create: `src/renderer/styles/global.css`

- [ ] **Step 1: Create index.html**

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Clinical Recall Assistant</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/renderer/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 2: Create global.css**

Create `src/renderer/styles/global.css`:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **Step 3: Create main.tsx**

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles/global.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

- [ ] **Step 4: Create App.tsx**

```tsx
import { useEffect, useState } from "react";

type BackendStatus = "checking" | "connected" | "unavailable";

// Retries handle the case where Python is still starting when React mounts.
async function pollHealth(maxAttempts = 3, delayMs = 800): Promise<boolean> {
  for (let i = 0; i < maxAttempts; i++) {
    try {
      const res = await fetch("http://localhost:7777/health");
      if (res.ok) {
        await res.json();
        return true;
      }
    } catch {
      // Backend not ready yet — will retry.
    }
    if (i < maxAttempts - 1) {
      await new Promise((resolve) => setTimeout(resolve, delayMs));
    }
  }
  return false;
}

export default function App() {
  const [status, setStatus] = useState<BackendStatus>("checking");

  useEffect(() => {
    pollHealth().then((ok) => setStatus(ok ? "connected" : "unavailable"));
  }, []);

  return (
    <div style={{ padding: "2rem", fontFamily: "sans-serif" }}>
      <h1>Clinical Recall Assistant</h1>
      <p>
        {status === "checking" && "Connecting to backend..."}
        {status === "connected" && "Backend connected"}
        {status === "unavailable" && "Backend unavailable"}
      </p>
    </div>
  );
}
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
npm test
```

Expected:
```
✓ tests/renderer/App.test.tsx (2)
  ✓ App > shows "Backend connected" when health check succeeds
  ✓ App > shows "Backend unavailable" when health check fails

Test Files  1 passed (1)
Tests       2 passed (2)
```

- [ ] **Step 6: Commit**

```bash
git add index.html src/renderer/ tests/renderer/ package.json tsconfig.json vite.config.ts tailwind.config.js
git commit -m "feat: add React renderer with backend health check, Vite + Tailwind setup"
```

---

## Task 7: Electron main process

**Files:**
- Create: `src/electron/main.js`
- Create: `src/electron/preload.js`

> Note: Electron main process cannot be unit tested in isolation. Verification is manual (Task 9 smoke test).

- [ ] **Step 1: Create main.js**

```js
const { app, BrowserWindow } = require("electron");
const { spawn } = require("child_process");
const path = require("path");

const isDev = process.env.NODE_ENV === "development";

let pythonProcess = null;
let mainWindow = null;

function startPython() {
  const scriptPath = isDev
    ? path.join(app.getAppPath(), "src/python/main.py")
    : path.join(process.resourcesPath, "src/python/main.py");

  pythonProcess = spawn("python3", [scriptPath]);

  pythonProcess.on("error", (err) => {
    console.error(`[Python] failed to start: ${err.message}`);
    console.error("[Python] Ensure python3 is installed and on PATH.");
  });

  pythonProcess.stdout.on("data", (data) => {
    console.log(`[Python] ${data.toString().trim()}`);
  });

  pythonProcess.stderr.on("data", (data) => {
    console.error(`[Python stderr] ${data.toString().trim()}`);
  });

  pythonProcess.on("close", (code) => {
    console.log(`[Python] process exited with code ${code}`);
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  const url = isDev
    ? "http://localhost:5173"
    : `file://${path.join(app.getAppPath(), "dist/index.html")}`;

  mainWindow.loadURL(url);
}

app.whenReady().then(() => {
  startPython();
  createWindow();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("quit", () => {
  if (pythonProcess) {
    pythonProcess.kill();
  }
});
```

- [ ] **Step 2: Create preload.js**

```js
const { contextBridge } = require("electron");

// Placeholder — IPC methods will be added in later phases
contextBridge.exposeInMainWorld("api", {});
```

- [ ] **Step 3: Commit**

```bash
git add src/electron/
git commit -m "feat: add Electron main process with Python spawn and BrowserWindow"
```

---

## Task 8: Config, directories, and settings

**Files:**
- Create: `config/settings.example.json`
- Create: `config/settings.json`
- Create: `data/cmgs/.gitkeep`
- Create: `data/notes_md/.gitkeep`
- Create: `data/chroma_db/.gitkeep`

- [ ] **Step 1: Create data directories with gitkeep files**

```bash
mkdir -p data/cmgs data/notes_md data/chroma_db
touch data/cmgs/.gitkeep data/notes_md/.gitkeep data/chroma_db/.gitkeep
```

- [ ] **Step 2: Create config/settings.example.json**

Create `config/settings.example.json`:
```json
{
  "provider": "anthropic",
  "quiz_model": "claude-haiku-4-5",
  "clean_model": "claude-opus-4-5",
  "api_key": ""
}
```

- [ ] **Step 3: Create config/settings.json (gitignored)**

Create `config/settings.json` with the same content as `settings.example.json`. This file is gitignored and is where the user will add real API keys.

```json
{
  "provider": "anthropic",
  "quiz_model": "claude-haiku-4-5",
  "clean_model": "claude-opus-4-5",
  "api_key": ""
}
```

- [ ] **Step 4: Create renderer subdirectories**

```bash
mkdir -p src/renderer/components src/renderer/pages src/renderer/hooks
touch src/renderer/components/.gitkeep src/renderer/pages/.gitkeep src/renderer/hooks/.gitkeep
```

- [ ] **Step 5: Commit**

```bash
git add data/ config/settings.example.json src/renderer/components/.gitkeep src/renderer/pages/.gitkeep src/renderer/hooks/.gitkeep
git commit -m "chore: add data directories, config skeleton, and renderer subdirectories"
```

---

## Task 9: Smoke test and finalise TODO

**Files:**
- Modify: `TODO.md`

- [ ] **Step 1: Run full test suite**

```bash
npm test && pytest tests/python/ -v
```

Expected: all tests pass (2 renderer + 2 Python = 4 total).

- [ ] **Step 2: Smoke test the running app**

```bash
npm run dev
```

Expected:
- Terminal shows Vite dev server starting on `http://localhost:5173`
- Terminal shows `[Python] INFO: Started server process`
- Electron window opens showing "Clinical Recall Assistant"
- Window shows **"Backend connected"** (not "Backend unavailable")

If "Backend unavailable" appears: check Python console output. Common cause: Python not installed or port conflict on 7777.

- [ ] **Step 3: Verify health endpoint directly**

While `npm run dev` is running, in a separate terminal:
```bash
curl http://localhost:7777/health
```

Expected: `{"status":"ok","version":"0.1.0"}`

- [ ] **Step 4: Update TODO.md**

Mark these Phase 0 items as complete (`[x]`):
- `[ ] Initialise git repository` → `[x]`
- `[ ] Confirm technology stack (GUI framework, bundler, etc.)` → `[x]`
- `[ ] Set up project scaffolding (package.json / pyproject.toml, directory structure)` → `[x]`
- `[ ] Create InfoERRORS.md for user-flagged corrections` → `[x]` (was already present)

Update the `Last Updated` date to today.

- [ ] **Step 5: Final commit**

```bash
git add TODO.md
git commit -m "chore: mark Phase 0 complete in TODO"
```
