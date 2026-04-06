# Clinical Guidelines Page — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a `/guidelines` page that lets users browse all CMGs, medicine monographs, and clinical skills as a card grid grouped by section, with a side-panel detail view and quiz launch with scope picker.

**Architecture:** New FastAPI router reads structured JSON from `data/cmgs/structured/` and serves list + detail endpoints. React page consumes them via `useApi`, renders a filterable card grid with side panel overlay. Quiz launch navigates to existing `/quiz` route with scope state.

**Tech Stack:** FastAPI + Pydantic (backend), React 19 + TypeScript + Tailwind (frontend), vitest + @testing-library/react (frontend tests), pytest + httpx (backend tests)

---

## File Structure

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `src/python/guidelines/__init__.py` | Python package marker |
| Create | `src/python/guidelines/models.py` | Pydantic response models |
| Create | `src/python/guidelines/router.py` | `/guidelines` list + detail endpoints |
| Modify | `src/python/main.py` | Mount guidelines router |
| Create | `tests/python/test_guidelines_router.py` | Backend endpoint tests |
| Add | `src/renderer/types/api.ts` | `GuidelineSummary` + `GuidelineDetail` interfaces |
| Create | `src/renderer/pages/Guidelines.tsx` | Full guidelines page with card grid, filters, side panel |
| Modify | `src/renderer/App.tsx` | Add `/guidelines` route |
| Modify | `src/renderer/components/Sidebar.tsx` | Update nav label + path |
| Modify | `tests/renderer/Sidebar.test.tsx` | Update nav assertion |
| Create | `tests/renderer/Guidelines.test.tsx` | Frontend page tests |

---

### Task 1: Backend — Pydantic Response Models

**Files:**
- Create: `src/python/guidelines/__init__.py`
- Create: `src/python/guidelines/models.py`
- Test: `tests/python/test_guidelines_router.py` (written in Task 2)

- [ ] **Step 1: Create the package `__init__.py`**

```python
# src/python/guidelines/__init__.py
```

Empty file — just a package marker.

- [ ] **Step 2: Create `models.py` with response models**

```python
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class GuidelineSummary(BaseModel):
    id: str
    cmg_number: str
    title: str
    section: str
    source_type: str


class GuidelineDetail(BaseModel):
    id: str
    cmg_number: str
    title: str
    section: str
    source_type: str
    content_markdown: str
    dose_lookup: Optional[dict] = None
    flowchart: Optional[dict] = None
```

- [ ] **Step 3: Verify models import cleanly**

Run: `PYTHONPATH=src/python python3 -c "from guidelines.models import GuidelineSummary, GuidelineDetail; print('OK')"`
Expected: `OK`

---

### Task 2: Backend — Guidelines Router

**Files:**
- Create: `src/python/guidelines/router.py`
- Create: `tests/python/test_guidelines_router.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/python/test_guidelines_router.py
from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport

from main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.anyio
async def test_list_guidelines(client: AsyncClient):
    resp = await client.get("/guidelines")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    if data:
        first = data[0]
        assert "id" in first
        assert "cmg_number" in first
        assert "title" in first
        assert "section" in first
        assert "source_type" in first


@pytest.mark.anyio
async def test_list_guidelines_type_filter(client: AsyncClient):
    resp = await client.get("/guidelines", params={"type": "med"})
    assert resp.status_code == 200
    data = resp.json()
    for item in data:
        assert item["source_type"] == "med"


@pytest.mark.anyio
async def test_list_guidelines_section_filter(client: AsyncClient):
    resp = await client.get("/guidelines", params={"section": "Cardiac"})
    assert resp.status_code == 200
    data = resp.json()
    for item in data:
        assert item["section"] == "Cardiac"


@pytest.mark.anyio
async def test_get_guideline_detail(client: AsyncClient):
    list_resp = await client.get("/guidelines")
    items = list_resp.json()
    if not items:
        pytest.skip("No guidelines data available")
    first_id = items[0]["id"]
    resp = await client.get(f"/guidelines/{first_id}")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["id"] == first_id
    assert "content_markdown" in detail


@pytest.mark.anyio
async def test_get_guideline_detail_not_found(client: AsyncClient):
    resp = await client.get("/guidelines/nonexistent_id")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src/python python3 -m pytest tests/python/test_guidelines_router.py -v`
Expected: FAIL — module `guidelines.router` not found (router not mounted yet)

- [ ] **Step 3: Create `router.py`**

```python
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from .models import GuidelineDetail, GuidelineSummary

router = APIRouter(prefix="/guidelines", tags=["guidelines"])

STRUCTURED_DIR = Path("data/cmgs/structured")

_TYPE_DIRS = {
    "cmg": STRUCTURED_DIR,
    "med": STRUCTURED_DIR / "med",
    "csm": STRUCTURED_DIR / "csm",
}


def _load_all_raw() -> list[dict]:
    results: list[dict] = []
    for source_type, directory in _TYPE_DIRS.items():
        if not directory.exists():
            continue
        for fpath in sorted(directory.glob("*.json")):
            try:
                with open(fpath, encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue
            data["_source_type"] = source_type
            data["_file_path"] = fpath
            results.append(data)
    return results


@router.get("")
def list_guidelines(
    type: str | None = None,
    section: str | None = None,
) -> list[dict]:
    raw = _load_all_raw()
    summaries: list[dict] = []
    for item in raw:
        source_type = item.get("_source_type", "cmg")
        if type and source_type != type:
            continue
        if section and item.get("section", "") != section:
            continue
        summaries.append(
            GuidelineSummary(
                id=item["id"],
                cmg_number=item.get("cmg_number", ""),
                title=item.get("title", ""),
                section=item.get("section", "Other"),
                source_type=source_type,
            ).model_dump()
        )
    return summaries


@router.get("/{guideline_id}")
def get_guideline(guideline_id: str) -> dict:
    for source_type, directory in _TYPE_DIRS.items():
        if not directory.exists():
            continue
        for fpath in directory.glob("*.json"):
            if fpath.stem == guideline_id:
                try:
                    with open(fpath, encoding="utf-8") as f:
                        data = json.load(f)
                except (json.JSONDecodeError, OSError):
                    raise HTTPException(status_code=500, detail="Failed to read guideline")
                return GuidelineDetail(
                    id=data["id"],
                    cmg_number=data.get("cmg_number", ""),
                    title=data.get("title", ""),
                    section=data.get("section", "Other"),
                    source_type=source_type,
                    content_markdown=data.get("content_markdown", ""),
                    dose_lookup=data.get("dose_lookup"),
                    flowchart=data.get("flowchart"),
                ).model_dump()
    raise HTTPException(status_code=404, detail="Guideline not found")
```

- [ ] **Step 4: Mount the router in `main.py`**

Add to `src/python/main.py` after the existing imports (line 18):

```python
from guidelines.router import router as guidelines_router
```

Add after line 23 (`app.include_router(search_router)`):

```python
app.include_router(guidelines_router)
```

The full `main.py` becomes:

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

from medication.router import router as medication_router
from quiz.router import router as quiz_router
from search.router import router as search_router
from settings.router import router as settings_router
from guidelines.router import router as guidelines_router

app.include_router(quiz_router)
app.include_router(settings_router)
app.include_router(medication_router)
app.include_router(search_router)
app.include_router(guidelines_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": "0.1.0"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=7777, reload=False)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `PYTHONPATH=src/python python3 -m pytest tests/python/test_guidelines_router.py -v`
Expected: All 5 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/python/guidelines/ src/python/main.py tests/python/test_guidelines_router.py
git commit -m "feat: add /guidelines backend router with list and detail endpoints"
```

---

### Task 3: Frontend — Types and Route

**Files:**
- Modify: `src/renderer/types/api.ts` (add types at end)
- Modify: `src/renderer/App.tsx` (add route)
- Modify: `src/renderer/components/Sidebar.tsx` (update nav label + path)
- Modify: `tests/renderer/Sidebar.test.tsx` (update assertion)

- [ ] **Step 1: Add TypeScript interfaces to `api.ts`**

Append to end of `src/renderer/types/api.ts`:

```typescript
export interface GuidelineSummary {
  id: string;
  cmg_number: string;
  title: string;
  section: string;
  source_type: "cmg" | "med" | "csm";
}

export interface GuidelineDetail {
  id: string;
  cmg_number: string;
  title: string;
  section: string;
  source_type: "cmg" | "med" | "csm";
  content_markdown: string;
  dose_lookup: Record<string, unknown> | null;
  flowchart: Record<string, unknown> | null;
}
```

- [ ] **Step 2: Add route to `App.tsx`**

In `src/renderer/App.tsx`, add import after line 9:

```typescript
import Guidelines from "./pages/Guidelines";
```

Add route inside `StandardLayout`'s `<Routes>` block (after line 18):

```tsx
<Route path="/guidelines" element={<Guidelines />} />
```

- [ ] **Step 3: Update Sidebar nav item**

In `src/renderer/components/Sidebar.tsx`, change the second `primaryNav` entry (line 12) from:

```typescript
  { icon: "clinical_notes", label: "Clinical Guidelines", path: "/guidelines" },
```

(This was previously `"Clinical Protocols"` pointing to `/quiz` — now it says `"Clinical Guidelines"` and points to `/guidelines`.)

- [ ] **Step 4: Update Sidebar test**

In `tests/renderer/Sidebar.test.tsx`, change the assertion for the nav item (line 32) to:

```typescript
    expect(screen.getByText("Clinical Guidelines")).toBeInTheDocument();
```

- [ ] **Step 5: Run tests to verify**

Run: `npx vitest run tests/renderer/Sidebar.test.tsx`
Expected: All 6 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/renderer/types/api.ts src/renderer/App.tsx src/renderer/components/Sidebar.tsx tests/renderer/Sidebar.test.tsx
git commit -m "feat: add /guidelines route and update sidebar navigation"
```

---

### Task 4: Frontend — Guidelines Page Component

**Files:**
- Create: `src/renderer/pages/Guidelines.tsx`
- Create: `tests/renderer/Guidelines.test.tsx`

This is the largest task. The page has four main concerns: filter bar, grouped card grid, side panel, and quiz scope picker.

- [ ] **Step 1: Write the failing frontend tests**

```typescript
// tests/renderer/Guidelines.test.tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { ThemeProvider } from "../../src/renderer/hooks/useTheme";
import AppShell from "../../src/renderer/components/AppShell";
import Guidelines from "../../src/renderer/pages/Guidelines";

const mockGuidelines = [
  { id: "CMG_4_Cardiac_Arrest", cmg_number: "4", title: "Cardiac Arrest – Adult", section: "Cardiac", source_type: "cmg" },
  { id: "CMG_23_Stroke", cmg_number: "23", title: "Stroke", section: "Neurology", source_type: "cmg" },
  { id: "CMG_03_Adrenaline", cmg_number: "03", title: "Adrenaline", section: "Medicine", source_type: "med" },
];

const mockDetail = {
  id: "CMG_4_Cardiac_Arrest",
  cmg_number: "4",
  title: "Cardiac Arrest – Adult",
  section: "Cardiac",
  source_type: "cmg",
  content_markdown: "#### Assessment\n- Unresponsive patient\n- Absent vital signs",
  dose_lookup: null,
  flowchart: null,
};

beforeEach(() => {
  global.fetch = vi.fn().mockImplementation((url: string) => {
    if (url.includes("/guidelines/") && !url.includes("type=")) {
      const id = url.split("/guidelines/")[1].split("?")[0];
      if (id === mockDetail.id) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(mockDetail) });
      }
      return Promise.resolve({ ok: false, status: 404 });
    }
    if (url.includes("/guidelines")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(mockGuidelines) });
    }
    return Promise.resolve({ ok: false, status: 404 });
  });
});

function renderGuidelines() {
  return render(
    <ThemeProvider>
      <MemoryRouter initialEntries={["/guidelines"]}>
        <Routes>
          <Route path="/*" element={<AppShell><Guidelines /></AppShell>} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>
  );
}

describe("Guidelines page", () => {
  it("renders the page title", async () => {
    renderGuidelines();
    expect(await screen.findByText("Clinical Guidelines")).toBeInTheDocument();
  });

  it("renders guideline cards after loading", async () => {
    renderGuidelines();
    expect(await screen.findByText("Cardiac Arrest – Adult")).toBeInTheDocument();
    expect(screen.getByText("Stroke")).toBeInTheDocument();
    expect(screen.getByText("Adrenaline")).toBeInTheDocument();
  });

  it("renders type filter chips", async () => {
    renderGuidelines();
    expect(await screen.findByText("All")).toBeInTheDocument();
    expect(screen.getByText("CMG")).toBeInTheDocument();
    expect(screen.getByText("Medication")).toBeInTheDocument();
    expect(screen.getByText("Clinical Skill")).toBeInTheDocument();
  });

  it("filters by type when CMG chip is clicked", async () => {
    renderGuidelines();
    await screen.findByText("Cardiac Arrest – Adult");
    fireEvent.click(screen.getByText("CMG"));
    expect(screen.getByText("Cardiac Arrest – Adult")).toBeInTheDocument();
    expect(screen.getByText("Stroke")).toBeInTheDocument();
    expect(screen.queryByText("Adrenaline")).not.toBeInTheDocument();
  });

  it("opens side panel when a card is clicked", async () => {
    renderGuidelines();
    await screen.findByText("Cardiac Arrest – Adult");
    fireEvent.click(screen.getByText("Cardiac Arrest – Adult"));
    expect(await screen.findByText("Assessment")).toBeInTheDocument();
    expect(screen.getByText("Start Revision")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run tests/renderer/Guidelines.test.tsx`
Expected: FAIL — module `../../src/renderer/pages/Guidelines` not found

- [ ] **Step 3: Create `Guidelines.tsx`**

```tsx
import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useApi } from "../hooks/useApi";
import { useApiMutation } from "../hooks/useApi";
import Tag from "../components/Tag";
import Card from "../components/Card";
import type { GuidelineSummary, GuidelineDetail } from "../types/api";

const SECTION_ORDER = [
  "Cardiac",
  "Respiratory",
  "Airway Management",
  "Neurology",
  "Trauma",
  "Medical",
  "Pain Management",
  "Toxicology",
  "Environmental",
  "Obstetric",
  "Behavioural",
  "HAZMAT",
  "Palliative Care",
  "General Care",
  "Other",
];

const TYPE_FILTERS = [
  { key: "all", label: "All" },
  { key: "cmg", label: "CMG" },
  { key: "med", label: "Medication" },
  { key: "csm", label: "Clinical Skill" },
] as const;

const TYPE_TAG_COLOUR: Record<string, string> = {
  cmg: "bg-primary/15 text-primary",
  med: "bg-tertiary-fixed/20 text-on-surface",
  csm: "bg-on-surface-variant/10 text-on-surface-variant",
};

export default function Guidelines() {
  const navigate = useNavigate();
  const { data: guidelines, loading, error } = useApi<GuidelineSummary[]>("/guidelines");

  const [selectedType, setSelectedType] = useState<string>("all");
  const [selectedSection, setSelectedSection] = useState<string>("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [scopePickerOpen, setScopePickerOpen] = useState(false);

  const { data: detail } = useApi<GuidelineDetail>(
    selectedId ? `/guidelines/${selectedId}` : ""
  );

  const filtered = useMemo(() => {
    if (!guidelines) return [];
    return guidelines.filter((g) => {
      if (selectedType !== "all" && g.source_type !== selectedType) return false;
      if (selectedSection !== "all" && g.section !== selectedSection) return false;
      return true;
    });
  }, [guidelines, selectedType, selectedSection]);

  const sections = useMemo(() => {
    const present = new Set(filtered.map((g) => g.section));
    return SECTION_ORDER.filter((s) => present.has(s));
  }, [filtered]);

  const grouped = useMemo(() => {
    const map = new Map<string, GuidelineSummary[]>();
    for (const g of filtered) {
      const arr = map.get(g.section) || [];
      arr.push(g);
      map.set(g.section, arr);
    }
    return map;
  }, [filtered]);

  const allSections = useMemo(() => {
    if (!guidelines) return [];
    const s = new Set(guidelines.map((g) => g.section));
    return Array.from(s).sort();
  }, [guidelines]);

  function handleStartRevision(scope: "guideline" | "section" | "all") {
    navigate("/quiz", {
      state: {
        scope,
        guidelineId: selectedId,
        section: detail?.section,
      },
    });
  }

  return (
    <div>
      <div className="mb-8">
        <span className="font-label text-label-sm text-on-surface-variant">
          Clinical Reference
        </span>
        <h2 className="font-headline text-display-lg text-primary">
          Clinical Guidelines
        </h2>
        <p className="font-body text-body-md text-on-surface-variant mt-1">
          Browse CMGs, medicine monographs, and clinical skills from ACTAS guidelines.
        </p>
      </div>

      {loading && (
        <div className="flex items-center justify-center h-32">
          <span className="font-mono text-[10px] text-on-surface-variant animate-pulse">
            Loading guidelines...
          </span>
        </div>
      )}

      {error && (
        <div className="flex items-center justify-center h-32">
          <span className="font-mono text-[10px] text-status-critical">{error}</span>
        </div>
      )}

      {guidelines && (
        <>
          <div className="flex items-center gap-4 mb-8 flex-wrap">
            <div className="flex gap-2">
              {TYPE_FILTERS.map((tf) => (
                <button
                  key={tf.key}
                  onClick={() => setSelectedType(tf.key)}
                  className={`px-3 py-1.5 font-label text-[10px] uppercase tracking-widest transition-colors ${
                    selectedType === tf.key
                      ? "bg-primary text-on-primary"
                      : "bg-surface-container-low text-on-surface-variant hover:bg-surface-container-lowest"
                  }`}
                >
                  {tf.label}
                </button>
              ))}
            </div>

            <select
              value={selectedSection}
              onChange={(e) => setSelectedSection(e.target.value)}
              className="bg-surface-container-low text-on-surface font-label text-[10px] uppercase tracking-widest px-3 py-1.5 appearance-none cursor-pointer"
            >
              <option value="all">All Sections</option>
              {allSections.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>

            <span className="font-mono text-[10px] text-on-surface-variant ml-auto">
              {filtered.length} guidelines
            </span>
          </div>

          {sections.length === 0 && (
            <div className="text-center py-12">
              <p className="font-body text-body-md text-on-surface-variant">
                No guidelines match the current filters.
              </p>
            </div>
          )}

          {sections.map((section) => (
            <div key={section} className="mb-10">
              <h3 className="font-headline text-title-lg text-on-surface-variant mb-4">
                {section}
              </h3>
              <div className="grid grid-cols-3 gap-4">
                {(grouped.get(section) || []).map((g) => (
                  <Card
                    key={g.id}
                    onClick={() => {
                      setSelectedId(g.id);
                      setScopePickerOpen(false);
                    }}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <span className="font-mono text-[10px] text-on-surface-variant">
                        CMG {g.cmg_number}
                      </span>
                      <span
                        className={`font-label text-[9px] uppercase tracking-widest px-2 py-0.5 rounded-sm ${
                          TYPE_TAG_COLOUR[g.source_type] || ""
                        }`}
                      >
                        {g.source_type === "csm"
                          ? "Skill"
                          : g.source_type === "med"
                          ? "Med"
                          : "CMG"}
                      </span>
                    </div>
                    <h4 className="font-headline text-body-lg text-primary truncate">
                      {g.title}
                    </h4>
                  </Card>
                ))}
              </div>
            </div>
          ))}
        </>
      )}

      {selectedId && detail && (
        <>
          <div
            className="fixed inset-0 bg-on-surface/20 z-40"
            onClick={() => {
              setSelectedId(null);
              setScopePickerOpen(false);
            }}
          />
          <div className="fixed right-0 top-0 h-screen w-[40%] min-w-[480px] bg-surface-container-low z-50 flex flex-col overflow-hidden shadow-2xl">
            <div className="p-8 pb-4 flex items-start justify-between">
              <div>
                <span className="font-mono text-[10px] text-on-surface-variant">
                  CMG {detail.cmg_number}
                </span>
                <h2 className="font-headline text-title-xl text-primary mt-1">
                  {detail.title}
                </h2>
                <span className="font-label text-[10px] uppercase tracking-widest text-on-surface-variant mt-1 block">
                  {detail.section}
                </span>
              </div>
              <button
                onClick={() => {
                  setSelectedId(null);
                  setScopePickerOpen(false);
                }}
                className="text-on-surface-variant hover:text-primary transition-colors p-1"
                aria-label="Close"
              >
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-8 pb-8">
              <div className="prose prose-sm max-w-none font-body text-on-surface">
                {detail.content_markdown.split("\n").map((line, i) => {
                  if (line.startsWith("#### ")) {
                    return (
                      <h4 key={i} className="font-headline text-body-lg text-primary mt-6 mb-2">
                        {line.replace("#### ", "")}
                      </h4>
                    );
                  }
                  if (line.startsWith("- ") || line.startsWith("* ")) {
                    return (
                      <p key={i} className="pl-4 text-body-md text-on-surface leading-relaxed">
                        {line.replace(/^[-*]\s*/, "")}
                      </p>
                    );
                  }
                  if (line.trim() === "") return null;
                  return (
                    <p key={i} className="text-body-md text-on-surface leading-relaxed">
                      {line}
                    </p>
                  );
                })}
              </div>
            </div>

            <div className="p-6 border-t border-outline-variant/15 bg-surface-container-low">
              {scopePickerOpen && (
                <div className="flex gap-2 mb-3">
                  <button
                    onClick={() => handleStartRevision("guideline")}
                    className="flex-1 px-3 py-2 bg-surface-container-lowest text-on-surface font-label text-[10px] uppercase tracking-widest hover:bg-primary hover:text-on-primary transition-colors"
                  >
                    This Guideline
                  </button>
                  <button
                    onClick={() => handleStartRevision("section")}
                    className="flex-1 px-3 py-2 bg-surface-container-lowest text-on-surface font-label text-[10px] uppercase tracking-widest hover:bg-primary hover:text-on-primary transition-colors"
                  >
                    This Section
                  </button>
                  <button
                    onClick={() => handleStartRevision("all")}
                    className="flex-1 px-3 py-2 bg-surface-container-lowest text-on-surface font-label text-[10px] uppercase tracking-widest hover:bg-primary hover:text-on-primary transition-colors"
                  >
                    All Guidelines
                  </button>
                </div>
              )}
              <button
                onClick={() => setScopePickerOpen(!scopePickerOpen)}
                className="w-full bg-primary text-on-primary py-3 px-4 font-label text-xs uppercase tracking-[0.2em] hover:opacity-90 transition-opacity"
              >
                Start Revision
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run frontend typecheck**

Run: `npx tsc --noEmit`
Expected: No errors

- [ ] **Step 5: Run the failing tests**

Run: `npx vitest run tests/renderer/Guidelines.test.tsx`
Expected: All 5 tests PASS

- [ ] **Step 6: Run all frontend tests to check for regressions**

Run: `npx vitest run`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/renderer/pages/Guidelines.tsx tests/renderer/Guidelines.test.tsx
git commit -m "feat: add Clinical Guidelines page with card grid, filters, side panel, and quiz launcher"
```

---

### Task 5: Regression Check

**Files:** None (verification only)

- [ ] **Step 1: Run full backend test suite**

Run: `PYTHONPATH=src/python python3 -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 2: Run full frontend test suite**

Run: `npx vitest run`
Expected: All tests PASS

- [ ] **Step 3: Run TypeScript typecheck**

Run: `npx tsc --noEmit`
Expected: No errors
