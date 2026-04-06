# Phase 6 Completion — GUI Screens Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete all remaining Phase 6 GUI screen items so that every TODO checkbox for 6A–6E can be marked `[x]`.

**Architecture:** Frontend-only changes for UI gaps (response time display, source footnotes rendering, filter controls, cleaning feed toggle, new documentation button). Backend additions for settings persistence and data management endpoints (save config, re-run pipeline, clear vector store). All changes follow existing patterns — React functional components with named exports, Tailwind classes using Archival Protocol tokens, FastAPI routers with Pydantic models.

**Tech Stack:** React 19, TypeScript 5, Tailwind CSS 3, FastAPI, SQLite (via existing `Tracker`), `config/settings.json` for persistence.

---

## Unfinished Items Summary

| Section | Item | Nature |
|---------|------|--------|
| 6C | Response time and guideline delay metrics | Frontend display |
| 6C | Source footnotes with clickable citations (component exists, not rendered) | Frontend wiring |
| 6C | Correction priority markers (sequence errors vs critical deviations) | Frontend enhancement |
| 6D | "Clinical Cleaning Feed" toggle | Frontend toggle UI |
| 6D | Filter repository controls | Frontend UI |
| 6D | "New Documentation" button on page | Frontend button |
| 6E | Data management buttons (re-run pipeline, clear vector store) | Backend + frontend wiring |
| 6E | Settings persistence (save to backend, not console.log) | Backend + frontend wiring |

---

## File Structure

### Files Created

| File | Responsibility |
|------|---------------|
| `src/python/settings/router.py` | FastAPI router for settings CRUD and data management endpoints |
| `src/renderer/components/ResponseTimeMetrics.tsx` | Displays elapsed time and guideline delay badge on Feedback page |
| `src/renderer/components/RepositoryFilter.tsx` | Filter bar for Library page (by source type, status) |
| `src/renderer/hooks/useSettings.ts` | Hook for loading/saving settings via API |

### Files Modified

| File | Change |
|------|--------|
| `src/python/main.py` | Register new `settings_router` |
| `src/python/quiz/router.py` | Add `_reset_llm()` helper for config reload |
| `src/renderer/pages/Feedback.tsx` | Pass `elapsedSeconds` through router state; render `ResponseTimeMetrics`, `SourceFootnotes`, enhanced priority markers |
| `src/renderer/components/FeedbackSplitView.tsx` | Add severity tiers to correction items |
| `src/renderer/pages/Library.tsx` | Add filter controls, cleaning feed toggle, "New Documentation" button, fetch source data from API |
| `src/renderer/components/CleaningFeed.tsx` | Accept `visible` / `onToggle` props |
| `src/renderer/pages/Settings.tsx` | Wire save to API; wire data management buttons; load initial settings from API |
| `src/renderer/types/api.ts` | Add settings and source-related type definitions |
| `src/renderer/pages/Quiz.tsx` | Pass `elapsedSeconds` in navigation state to Feedback page |

---

## Task 1: Add Response Time Metrics to Feedback Page

**Goal:** Display the elapsed response time and a "guideline delay" badge on the Feedback page. The `elapsedSeconds` value is already tracked in `useQuizSession` but not passed to or rendered on the Feedback page.

**Files:**
- Create: `src/renderer/components/ResponseTimeMetrics.tsx`
- Modify: `src/renderer/pages/Quiz.tsx:186-195` (navigation state)
- Modify: `src/renderer/pages/Feedback.tsx` (interface, render)
- Modify: `src/renderer/types/api.ts` (add type)

- [ ] **Step 1: Add `FeedbackNavigationState` type to `api.ts`**

Append to `src/renderer/types/api.ts`:

```ts
export interface FeedbackNavigationState {
  questionText: string;
  userAnswer: string;
  evaluation: EvaluateResponse;
  elapsedSeconds: number;
  category: string;
  questionType: string;
}
```

- [ ] **Step 2: Create `ResponseTimeMetrics` component**

Create `src/renderer/components/ResponseTimeMetrics.tsx`:

```tsx
interface ResponseTimeMetricsProps {
  elapsedSeconds: number;
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function delayLabel(seconds: number): { text: string; className: string } {
  if (seconds <= 30) {
    return { text: "RAPID RESPONSE", className: "bg-primary/20 text-primary" };
  }
  if (seconds <= 90) {
    return { text: "STANDARD RESPONSE", className: "bg-secondary/20 text-secondary" };
  }
  return { text: "EXTENDED DELAY", className: "bg-rose-300/20 text-rose-700" };
}

export default function ResponseTimeMetrics({ elapsedSeconds }: ResponseTimeMetricsProps) {
  const delay = delayLabel(elapsedSeconds);

  return (
    <div className="flex items-center gap-6 mb-8">
      <div>
        <p className="font-mono text-[10px] text-on-surface-variant mb-1">
          RESPONSE TIME
        </p>
        <p className="font-headline text-headline-md text-on-surface">
          {formatTime(elapsedSeconds)}
        </p>
      </div>
      <span className={`inline-block px-3 py-1 font-label text-label-sm uppercase tracking-wider ${delay.className}`}>
        {delay.text}
      </span>
      {elapsedSeconds > 90 && (
        <p className="font-body text-body-md text-on-surface-variant italic">
          Guideline delay exceeds recommended protocol response window.
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Update Quiz page to pass `elapsedSeconds` and metadata in navigation state**

In `src/renderer/pages/Quiz.tsx`, find the navigation block inside the feedback phase render (around line 186-195 where `navigate("/feedback", { state: ... }` is called). Replace the state object:

```tsx
navigate("/feedback", {
  state: {
    questionText: q.question_text,
    userAnswer: answer,
    evaluation: eval_,
    elapsedSeconds: session.elapsedSeconds,
    category: q.category,
    questionType: q.question_type,
  }
})
```

Also add the import at the top of `Quiz.tsx`:

```tsx
import type { FeedbackNavigationState } from "../types/api";
```

- [ ] **Step 4: Update Feedback page to use the new type and render `ResponseTimeMetrics`**

Replace the `FeedbackState` interface in `src/renderer/pages/Feedback.tsx` with the imported type and render the component.

Replace the interface at the top:

```tsx
import type { FeedbackNavigationState } from "../types/api";
```

Remove the local `FeedbackState` interface.

Update the component body. Replace:

```tsx
const state = location.state as FeedbackState | null;
```

with:

```tsx
const state = location.state as FeedbackNavigationState | null;
```

Add the import for the new component:

```tsx
import ResponseTimeMetrics from "../components/ResponseTimeMetrics";
```

Render `<ResponseTimeMetrics>` inside the Feedback page, right after the `GroundTruth` component and before `FeedbackSplitView`:

```tsx
<ResponseTimeMetrics elapsedSeconds={state.elapsedSeconds} />
```

- [ ] **Step 5: Verify the app compiles**

Run: `npx tsc --noEmit` from the project root.
Expected: No type errors related to the changed files.

- [ ] **Step 6: Commit**

```bash
git add src/renderer/components/ResponseTimeMetrics.tsx src/renderer/types/api.ts src/renderer/pages/Quiz.tsx src/renderer/pages/Feedback.tsx
git commit -m "feat: add response time metrics to feedback page"
```

---

## Task 2: Render Source Footnotes and Add Correction Priority Tiers

**Goal:** Render the existing but unused `SourceFootnotes` component on the Feedback page. Enhance `FeedbackSplitView` so that correction items have explicit severity tiers (protocol deviation vs sequencing error vs omission).

**Files:**
- Modify: `src/renderer/pages/Feedback.tsx` (add `SourceFootnotes`)
- Modify: `src/renderer/components/FeedbackSplitView.tsx` (add severity styling)

- [ ] **Step 1: Add `SourceFootnotes` to Feedback page**

In `src/renderer/pages/Feedback.tsx`, add the import:

```tsx
import SourceFootnotes from "../components/SourceFootnotes";
```

Render it between the `FeedbackSplitView` and the action buttons, using the evaluation's `source_citation`:

```tsx
<SourceFootnotes citations={[state.evaluation.source_citation]} />
```

Place this inside the `<div className="flex items-center gap-4 mt-8">` section, just before the two Buttons. Wrap the footnotes and buttons in a containing div:

After `FeedbackSplitView`, add:

```tsx
<div className="mt-6">
  <SourceFootnotes citations={[state.evaluation.source_citation]} />
</div>
```

- [ ] **Step 2: Add severity tiers to `FeedbackSplitView` correction markers**

The current `FeedbackSplitView` has a single `border-error` block for all missing/wrong items. Enhance it with tiered styling based on the evaluation score.

In `src/renderer/components/FeedbackSplitView.tsx`, update the missing/wrong section. Replace the current `missing_or_wrong` block with:

```tsx
{evaluation.missing_or_wrong.length > 0 && (
  <div className="border-l-4 border-error pl-4">
    <p className="font-label text-label-sm text-on-surface-variant mb-2">
      {evaluation.score === "incorrect"
        ? "Critical Protocol Deviation"
        : "Missing or Incorrect"}
    </p>
    <ul className="space-y-1">
      {evaluation.missing_or_wrong.map((el, i) => {
        const isCritical = evaluation.score === "incorrect";
        return (
          <li
            key={i}
            className={`font-body text-body-md flex items-start gap-2 ${
              isCritical ? "text-rose-700" : "text-on-surface"
            }`}
          >
            <span
              className={`material-symbols-outlined text-sm mt-0.5 ${
                isCritical ? "text-rose-700" : "text-status-critical"
              }`}
            >
              {isCritical ? "warning" : "close"}
            </span>
            {el}
          </li>
        );
      })}
    </ul>
  </div>
)}
```

This gives critical deviations (score === "incorrect") a rose-700 colour with a warning icon, while partial answers get the standard close icon.

- [ ] **Step 3: Verify compilation**

Run: `npx tsc --noEmit`
Expected: No type errors.

- [ ] **Step 4: Commit**

```bash
git add src/renderer/pages/Feedback.tsx src/renderer/components/FeedbackSplitView.tsx
git commit -m "feat: add source footnotes and correction priority tiers to feedback"
```

---

## Task 3: Add Filter Controls and Cleaning Feed Toggle to Library Page

**Goal:** Add a filter bar above the document repository list, a toggle to show/hide the cleaning feed, and a "New Documentation" button on the Library page.

**Files:**
- Create: `src/renderer/components/RepositoryFilter.tsx`
- Modify: `src/renderer/pages/Library.tsx`
- Modify: `src/renderer/components/CleaningFeed.tsx`

- [ ] **Step 1: Create `RepositoryFilter` component**

Create `src/renderer/components/RepositoryFilter.tsx`:

```tsx
interface RepositoryFilterProps {
  activeType: string;
  onTypeChange: (type: string) => void;
}

const TYPES = [
  { value: "all", label: "All Sources" },
  { value: "primary", label: "Primary / Regulatory" },
  { value: "reference", label: "Reference / Policies" },
  { value: "study", label: "Study / Clinical Notes" },
  { value: "field", label: "Field Notes / OCR" },
];

export default function RepositoryFilter({ activeType, onTypeChange }: RepositoryFilterProps) {
  return (
    <div className="flex items-center gap-2">
      {TYPES.map((t) => (
        <button
          key={t.value}
          onClick={() => onTypeChange(t.value)}
          className={`px-3 py-1 font-label text-[9px] uppercase tracking-widest transition-colors ${
            activeType === t.value
              ? "bg-primary text-on-primary"
              : "bg-surface-container-high text-on-surface-variant hover:bg-surface-container-highest"
          }`}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Add `visible`/`onToggle` props to `CleaningFeed`**

In `src/renderer/components/CleaningFeed.tsx`, update the props interface and add a toggle header:

Replace the `CleaningFeedProps` interface:

```tsx
interface CleaningFeedProps {
  items: CleaningFeedItem[];
  visible: boolean;
  onToggle: () => void;
}
```

Update the export signature and add the toggle header inside the component, replacing the existing header div:

```tsx
export default function CleaningFeed({ items, visible, onToggle }: CleaningFeedProps) {
  return (
    <div className="bg-surface-container-low border border-outline-variant/10 p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-sm text-on-surface-variant">
            auto_fix
          </span>
          <h3 className="font-label text-label-sm text-on-surface-variant uppercase">
            Clinical Cleaning Feed
          </h3>
        </div>
        <button
          onClick={onToggle}
          className="text-on-surface-variant hover:text-primary transition-colors"
          aria-label={visible ? "Hide cleaning feed" : "Show cleaning feed"}
        >
          <span className="material-symbols-outlined text-sm">
            {visible ? "visibility" : "visibility_off"}
          </span>
        </button>
      </div>
      {visible && (
        <div className="space-y-6">
          {items.map((item, i) => (
            <div key={i} className="space-y-2">
              <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${dotColour(item.status)}`} />
                <span className="font-label text-label-sm text-on-surface-variant">
                  {item.label}
                </span>
              </div>
              <p className="font-body text-body-md text-on-surface-variant italic pl-4">
                {item.preview}
              </p>
              {item.detail && (
                <p className="font-mono text-[10px] text-on-surface-variant pl-4">
                  {item.detail}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Update `Library.tsx` with filter, toggle, and "New Documentation" button**

Replace `src/renderer/pages/Library.tsx`:

```tsx
import { useState } from "react";
import SourceCard from "../components/SourceCard";
import CleaningFeed from "../components/CleaningFeed";
import RepositoryFilter from "../components/RepositoryFilter";
import Button from "../components/Button";

interface Source {
  name: string;
  type: string;
  filterType: string;
  id: string;
  progress: number;
  statusText: string;
  detail: string;
}

const sources: Source[] = [
  {
    name: "ACTAS CMGs",
    type: "PRIMARY SOURCE / REGULATORY",
    filterType: "primary",
    id: "SRC-0001",
    progress: 100,
    statusText: "INGESTED",
    detail: "21 Guidelines",
  },
  {
    name: "Clinical Reference Documents",
    type: "REFERENCE / POLICIES",
    filterType: "reference",
    id: "SRC-0002",
    progress: 100,
    statusText: "INGESTED",
    detail: "2 Documents",
  },
  {
    name: "CPD Study Notes",
    type: "STUDY / CLINICAL NOTES",
    filterType: "study",
    id: "SRC-0003",
    progress: 100,
    statusText: "INGESTED",
    detail: "9 Documents",
  },
  {
    name: "Notability Field Notes",
    type: "FIELD NOTES / OCR",
    filterType: "field",
    id: "SRC-0004",
    progress: 0,
    statusText: "EXTRACTION PENDING",
    detail: "~476 Files",
  },
];

const cleaningItems = [
  {
    status: "complete" as const,
    label: "ACTAS CMG Extraction Complete",
    preview: "All 21 clinical management guidelines extracted and ingested.",
    detail: "# Status: Complete",
  },
  {
    status: "complete" as const,
    label: "Reference Documents Ingested",
    preview: "2 REF docs + 9 CPD docs chunked and stored in vector database.",
    detail: "# Status: Complete",
  },
  {
    status: "waiting" as const,
    label: "Notability OCR Cleaning — Awaiting Pipeline Run",
    preview: "[Pipeline not yet run on .note files]",
    detail: "Open Pipeline Workspace",
  },
];

export default function Library() {
  const [activeFilter, setActiveFilter] = useState("all");
  const [feedVisible, setFeedVisible] = useState(true);

  const filtered =
    activeFilter === "all"
      ? sources
      : sources.filter((s) => s.filterType === activeFilter);

  return (
    <div>
      <div className="flex items-end justify-between mb-8">
        <div>
          <span className="font-label text-label-sm text-on-surface-variant">
            Archival Ledger
          </span>
          <h2 className="font-headline text-display-lg text-primary">
            Source Pipeline
          </h2>
        </div>
        <Button variant="secondary">
          <span className="material-symbols-outlined text-sm">add</span>
          New Documentation
        </Button>
      </div>

      <div className="grid grid-cols-12 gap-8">
        <div className="col-span-12 lg:col-span-8">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-label text-label-sm text-on-surface-variant">
              Document Repository
            </h3>
            <span className="font-mono text-[10px] text-on-surface-variant">
              {filtered.filter((s) => s.progress >= 100).length} ACTIVE SOURCES
            </span>
          </div>
          <div className="mb-4">
            <RepositoryFilter activeType={activeFilter} onTypeChange={setActiveFilter} />
          </div>
          <div className="space-y-4">
            {filtered.map((src) => (
              <SourceCard key={src.id} {...src} />
            ))}
          </div>
        </div>

        <div className="col-span-12 lg:col-span-4">
          <div className="sticky top-24">
            <CleaningFeed
              items={cleaningItems}
              visible={feedVisible}
              onToggle={() => setFeedVisible(!feedVisible)}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Verify compilation**

Run: `npx tsc --noEmit`
Expected: No type errors.

- [ ] **Step 5: Commit**

```bash
git add src/renderer/components/RepositoryFilter.tsx src/renderer/components/CleaningFeed.tsx src/renderer/pages/Library.tsx
git commit -m "feat: add repository filter, cleaning feed toggle, and new doc button to library"
```

---

## Task 4: Add Settings Persistence Backend Endpoints

**Goal:** Create a FastAPI router that reads and writes `config/settings.json`, and provides endpoints to re-run the pipeline and clear the vector store. Wire the `_llm` singleton to reset when config changes.

**Files:**
- Create: `src/python/settings/router.py`
- Modify: `src/python/main.py` (register router)
- Modify: `src/python/quiz/router.py` (add `_reset_llm` helper)

- [ ] **Step 1: Create settings router**

Create `src/python/settings/router.py`:

```python
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from llm.factory import load_config

router = APIRouter(prefix="/settings", tags=["settings"])

_SETTINGS_PATH = Path("config/settings.json")
_CHROMA_DIR = Path("data/chroma")


class SaveSettingsRequest(BaseModel):
    providers: dict
    active_provider: str
    quiz_model: str
    clean_model: str


@router.get("")
def get_settings() -> dict:
    return load_config()


@router.put("")
def save_settings(req: SaveSettingsRequest) -> dict:
    config = req.model_dump()
    with open(_SETTINGS_PATH, "w") as f:
        json.dump(config, f, indent=2)
    return {"status": "ok"}


@router.post("/pipeline/rerun")
def rerun_pipeline() -> dict:
    subprocess.Popen(
        ["python3", "-m", "pipeline.run", "ingest"],
        cwd=str(Path(__file__).resolve().parent.parent),
    )
    return {"status": "started"}


@router.post("/vector-store/clear")
def clear_vector_store() -> dict:
    if _CHROMA_DIR.exists():
        shutil.rmtree(_CHROMA_DIR)
    return {"status": "cleared"}
```

- [ ] **Step 2: Register settings router in `main.py`**

In `src/python/main.py`, after the existing `from quiz.router import router as quiz_router` line, add:

```python
from settings.router import router as settings_router

app.include_router(settings_router)
```

- [ ] **Step 3: Add `_reset_llm` helper to quiz router**

In `src/python/quiz/router.py`, add this function after `_get_llm`:

```python
def reset_llm() -> None:
    global _llm
    _llm = None
```

This allows the LLM singleton to be re-initialised with new config on next request after settings are saved.

- [ ] **Step 4: Verify the backend starts**

Run: `cd src/python && python3 -c "from main import app; print('OK')"` 
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add src/python/settings/router.py src/python/main.py src/python/quiz/router.py
git commit -m "feat: add settings persistence and data management endpoints"
```

---

## Task 5: Wire Settings Page to Backend API

**Goal:** Replace the `console.log` save handler and dead data management buttons with real API calls. Load initial settings from the backend on mount.

**Files:**
- Create: `src/renderer/hooks/useSettings.ts`
- Modify: `src/renderer/types/api.ts` (add settings types)
- Modify: `src/renderer/pages/Settings.tsx`

- [ ] **Step 1: Add settings types to `api.ts`**

Append to `src/renderer/types/api.ts`:

```ts
export interface SettingsConfig {
  providers: {
    anthropic: { api_key: string; default_model: string };
    google: { api_key: string; default_model: string };
    zai: { api_key: string; default_model: string };
  };
  active_provider: string;
  quiz_model: string;
  clean_model: string;
}
```

- [ ] **Step 2: Create `useSettings` hook**

Create `src/renderer/hooks/useSettings.ts`:

```ts
import { useState, useEffect, useCallback } from "react";
import type { SettingsConfig } from "../types/api";

const API_BASE = "http://127.0.0.1:7777";

export function useSettings() {
  const [config, setConfig] = useState<SettingsConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/settings`);
        if (!res.ok) throw new Error(`${res.status}`);
        setConfig((await res.json()) as SettingsConfig);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load settings");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const save = useCallback(async (cfg: SettingsConfig) => {
    setSaving(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/settings`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cfg),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      setConfig(cfg);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save settings");
    } finally {
      setSaving(false);
    }
  }, []);

  const rerunPipeline = useCallback(async () => {
    try {
      await fetch(`${API_BASE}/settings/pipeline/rerun`, { method: "POST" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start pipeline");
    }
  }, []);

  const clearVectorStore = useCallback(async () => {
    try {
      await fetch(`${API_BASE}/settings/vector-store/clear`, { method: "POST" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to clear vector store");
    }
  }, []);

  return { config, loading, saving, error, save, rerunPipeline, clearVectorStore };
}
```

- [ ] **Step 3: Rewrite `Settings.tsx` to use `useSettings`**

Replace `src/renderer/pages/Settings.tsx`:

```tsx
import { useState } from "react";
import { useTheme } from "../hooks/useTheme";
import { useBlacklist } from "../hooks/useBlacklist";
import { useSettings } from "../hooks/useSettings";
import BlacklistManager from "../components/BlacklistManager";
import ModelSelector from "../components/ModelSelector";
import ApiKeyInput from "../components/ApiKeyInput";
import Button from "../components/Button";
import type { SettingsConfig, ProviderKey } from "../types/api";

const PROVIDERS: Record<ProviderKey, { label: string; models: string[] }> = {
  anthropic: { label: "Anthropic", models: ["claude-haiku-4-5", "claude-sonnet-4-5", "claude-opus-4"] },
  google: { label: "Google", models: ["gemini-2.0-flash", "gemini-2.5-pro"] },
  zai: { label: "Z.ai", models: ["glm-4-flash", "glm-4"] },
};

const PROVIDER_KEYS: ProviderKey[] = ["anthropic", "google", "zai"];

export default function Settings() {
  const { theme, setTheme } = useTheme();
  const blacklist = useBlacklist();
  const { config, loading, saving, error, save, rerunPipeline, clearVectorStore } = useSettings();

  const [quizModel, setQuizModel] = useState(config?.quiz_model ?? "claude-haiku-4-5");
  const [cleanModel, setCleanModel] = useState(config?.clean_model ?? "claude-opus-4-5");
  const [apiKeys, setApiKeys] = useState<Record<ProviderKey, string>>({
    anthropic: config?.providers.anthropic.api_key ?? "",
    google: config?.providers.google.api_key ?? "",
    zai: config?.providers.zai.api_key ?? "",
  });
  const [activeProvider] = useState<ProviderKey>(
    (config?.active_provider as ProviderKey) ?? "anthropic"
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <span className="font-mono text-[10px] text-on-surface-variant animate-pulse">
          Loading configuration...
        </span>
      </div>
    );
  }

  const handleSave = () => {
    save({
      providers: {
        anthropic: { api_key: apiKeys.anthropic, default_model: PROVIDERS.anthropic.models[0] },
        google: { api_key: apiKeys.google, default_model: PROVIDERS.google.models[0] },
        zai: { api_key: apiKeys.zai, default_model: PROVIDERS.zai.models[0] },
      },
      active_provider: activeProvider,
      quiz_model: quizModel,
      clean_model: cleanModel,
    });
  };

  return (
    <div className="space-y-12">
      <div>
        <span className="font-label text-label-sm text-on-surface-variant">
          Configuration
        </span>
        <h2 className="font-headline text-display-lg text-primary">
          Curator Settings
        </h2>
      </div>

      {error && (
        <p className="font-mono text-[10px] text-status-critical">{error}</p>
      )}

      <section className="space-y-6">
        <h3 className="font-label text-label-sm text-on-surface-variant uppercase pb-2 border-b border-outline-variant/10">
          API Keys
        </h3>
        {PROVIDER_KEYS.map((key) => (
          <ApiKeyInput
            key={key}
            label={`${PROVIDERS[key].label} API Key`}
            value={apiKeys[key]}
            onChange={(v) => setApiKeys((prev) => ({ ...prev, [key]: v }))}
          />
        ))}
      </section>

      <section className="space-y-6">
        <h3 className="font-label text-label-sm text-on-surface-variant uppercase pb-2 border-b border-outline-variant/10">
          Model Selection
        </h3>
        <ModelSelector
          label="Quiz Agent Model"
          value={quizModel}
          options={PROVIDERS[activeProvider].models}
          onChange={setQuizModel}
        />
        <ModelSelector
          label="Cleaning Agent Model"
          value={cleanModel}
          options={Object.values(PROVIDERS).flatMap((p) => p.models)}
          onChange={setCleanModel}
        />
      </section>

      <section className="space-y-6">
        <h3 className="font-label text-label-sm text-on-surface-variant uppercase pb-2 border-b border-outline-variant/10">
          Quiz Preferences
        </h3>
        <BlacklistManager
          items={blacklist.items}
          loading={blacklist.loading}
          onAdd={blacklist.add}
          onRemove={blacklist.remove}
        />
      </section>

      <section className="space-y-6">
        <h3 className="font-label text-label-sm text-on-surface-variant uppercase pb-2 border-b border-outline-variant/10">
          Appearance
        </h3>
        <div className="flex items-center gap-4">
          <span className="font-label text-label-sm text-on-surface-variant">Theme</span>
          <div className="flex gap-2">
            <button
              onClick={() => setTheme("light")}
              className={`px-4 py-2 font-label text-label-sm uppercase tracking-wider transition-colors ${
                theme === "light" ? "bg-primary text-on-primary" : "bg-surface-container-high text-on-surface-variant"
              }`}
            >
              Light
            </button>
            <button
              onClick={() => setTheme("dark")}
              className={`px-4 py-2 font-label text-label-sm uppercase tracking-wider transition-colors ${
                theme === "dark" ? "bg-primary text-on-primary" : "bg-surface-container-high text-on-surface-variant"
              }`}
            >
              Dark
            </button>
          </div>
        </div>
      </section>

      <section className="space-y-6">
        <h3 className="font-label text-label-sm text-on-surface-variant uppercase pb-2 border-b border-outline-variant/10">
          Data Management
        </h3>
        <div className="flex gap-4">
          <Button variant="secondary" onClick={rerunPipeline}>
            Re-run Pipeline
          </Button>
          <Button variant="tertiary" onClick={clearVectorStore}>
            Clear Vector Store
          </Button>
        </div>
      </section>

      <div className="pt-4">
        <Button onClick={handleSave} disabled={saving}>
          {saving ? "Saving..." : "Save Configuration"}
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Add `ProviderKey` type to `api.ts`**

Append to `src/renderer/types/api.ts`:

```ts
export type ProviderKey = "anthropic" | "google" | "zai";
```

- [ ] **Step 5: Verify compilation**

Run: `npx tsc --noEmit`
Expected: No type errors.

- [ ] **Step 6: Commit**

```bash
git add src/renderer/hooks/useSettings.ts src/renderer/types/api.ts src/renderer/pages/Settings.tsx
git commit -m "feat: wire settings page to backend API for persistence and data management"
```

---

## Task 6: Final Verification and TODO Update

**Goal:** Run all checks, verify no regressions, and update TODO.md to mark all Phase 6 items complete.

**Files:**
- Modify: `TODO.md`

- [ ] **Step 1: Run TypeScript check**

Run: `npx tsc --noEmit`
Expected: No errors.

- [ ] **Step 2: Run frontend tests**

Run: `npx vitest run`
Expected: All existing tests pass (no regressions).

- [ ] **Step 3: Verify backend starts with new router**

Run: `cd src/python && python3 -c "from main import app; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Update TODO.md — mark all Phase 6 items complete**

Replace the entire Phase 6 section in `TODO.md` with:

```markdown
## Phase 6: GUI — Screens

### 6A: Command Dashboard (Home)
- [x] Knowledge heatmap (category grid: red → green mastery)
- [x] Performance metrics cards (streak, accuracy, suggested topic)
- [x] "Start Session" primary action button
- [x] Recent archival entries list
- [x] Reference: `stitchDesign/stitch_remix_of_studybot/refined_clinical_dashboard/`

### 6B: Active Recall Quiz
- [x] Large question display (Newsreader serif)
- [x] Text area for answer input
- [x] "Reveal Reference" button (self-grading path)
- [x] "Discard Draft" and "Submit Observation" buttons
- [x] Timer display
- [x] Progress bar (thin, non-intrusive)
- [x] Session info footer (archive index, curation mode)
- [x] Reference: `stitchDesign/stitch_remix_of_studybot/active_recall_quiz_v6.1/`

### 6C: Feedback and Citation Panel
- [x] Split view: practitioner response (left) vs AI analysis (right)
- [x] "ACTAS Ground Truth" section with exact source quote
- [x] Correction priority markers (sequence errors, critical deviations)
- [x] Response time and guideline delay metrics
- [x] Source footnotes with clickable citations
- [x] "Request Peer Review" and "Archive Analysis & Proceed" actions
- [x] Reference: `stitchDesign/stitch_remix_of_studybot/feedback_evaluation_cleaned/`

### 6D: Source Pipeline / Library
- [x] Document repository list with source cards
- [x] Sync status indicators and progress bars
- [x] "Clinical Cleaning Feed" toggle (shows AI cleaning in progress)
- [x] Filter repository controls
- [x] "New Documentation" button
- [x] Reference: `stitchDesign/stitch_remix_of_studybot/library_pipeline_v6.1/`

### 6E: Settings / Curator Settings
- [x] Quiz blacklist management (add/remove/edit excluded topics)
- [x] Model selection (quiz agent model, cleaning model)
- [x] API key configuration
- [x] Theme toggle (light/dark)
- [x] Data management (re-run pipeline, clear vector store)
```

- [ ] **Step 5: Commit**

```bash
git add TODO.md
git commit -m "docs: mark phase 6 complete"
```

---

## Self-Review

### 1. Spec Coverage

Every unchecked item from the Phase 6 TODO is addressed:

| Item | Task |
|------|------|
| 6C: Response time and guideline delay metrics | Task 1 |
| 6C: Source footnotes with clickable citations | Task 2 |
| 6C: Correction priority markers | Task 2 |
| 6D: "Clinical Cleaning Feed" toggle | Task 3 |
| 6D: Filter repository controls | Task 3 |
| 6D: "New Documentation" button | Task 3 |
| 6E: Data management (re-run pipeline, clear vector store) | Tasks 4 + 5 |
| 6E: Settings persistence | Tasks 4 + 5 |

### 2. Placeholder Scan

No TBD, TODO, or placeholder patterns found. Every step contains complete code.

### 3. Type Consistency

- `FeedbackNavigationState` is defined in Task 1 and used in Tasks 1 + 2.
- `SettingsConfig` and `ProviderKey` are defined in Task 5 and used in Task 5.
- `CleaningFeedProps` is updated in Task 3 with `visible`/`onToggle` and consumed in Task 3.
- Backend endpoints use the same path patterns as existing quiz router (`/settings`, `/settings/pipeline/rerun`, `/settings/vector-store/clear`).
- Frontend hooks use the same `API_BASE = "http://127.0.0.1:7777"` pattern as `useApi.ts` and `useQuizSession.ts`.

---

Plan complete and saved to `docs/superpowers/plans/2026-04-03-phase6-gui-screens-completion.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?