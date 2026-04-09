# Phase 5: GUI Application Shell — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the desktop application shell with "The Archival Protocol" design system, persistent sidebar navigation, dark mode, and client-side routing — ready for Phase 6 screen implementations.

**Architecture:** React 19 + TypeScript renderer inside Electron 32. Tailwind CSS 3 provides design tokens sourced from CSS custom properties (enabling dark mode via class toggle). React Router v7 handles client-side navigation. A ThemeProvider context manages light/dark mode. Reusable component primitives (Button, Input, Card, Sidebar, SearchBar) form the design system layer. Page stubs render empty containers for Phase 6.

**Tech Stack:** React 19, TypeScript 5, Tailwind CSS 3 (darkMode: "class"), React Router v7, Material Symbols (icon font), Google Fonts (Newsreader, Space Grotesk, IBM Plex Mono)

---

## File Map

| File | Created/Modified | Responsibility |
|------|-----------------|----------------|
| `package.json` | Modify | Add react-router-dom dependency |
| `tailwind.config.js` | Modify | Full Archival Protocol tokens + dark mode colors |
| `postcss.config.js` | Create | PostCSS config for Tailwind |
| `src/renderer/styles/global.css` | Modify | CSS custom properties (light + dark), font imports, dot-grid, marginalia, base styles |
| `src/renderer/styles/tailwind.css` | Create | Tailwind layer imports (base, components, utilities) |
| `src/renderer/hooks/useTheme.tsx` | Create | ThemeProvider context + useTheme hook + dark mode toggle |
| `src/renderer/components/Button.tsx` | Create | 3-variant button (primary, secondary, tertiary) per DESIGN.md |
| `src/renderer/components/Input.tsx` | Create | "Field Note" style input with bottom-border per DESIGN.md |
| `src/renderer/components/Card.tsx` | Create | Document-stack card with hover lift per DESIGN.md |
| `src/renderer/components/Sidebar.tsx` | Create | Persistent left sidebar with nav items + active state |
| `src/renderer/components/SearchBar.tsx` | Create | Universal search input |
| `src/renderer/components/AppShell.tsx` | Create | Layout wrapper: Sidebar + SearchBar + content area |
| `src/renderer/components/MasteryIndicator.tsx` | Create | Progress bar + status dot for heatmap cards |
| `src/renderer/components/Tag.tsx` | Create | Small label/tag chip for categories and metadata |
| `src/renderer/pages/Dashboard.tsx` | Create | Empty page stub for Phase 6A |
| `src/renderer/pages/Quiz.tsx` | Create | Empty page stub for Phase 6B |
| `src/renderer/pages/Feedback.tsx` | Create | Empty page stub for Phase 6C |
| `src/renderer/pages/Library.tsx` | Create | Empty page stub for Phase 6D |
| `src/renderer/pages/Settings.tsx` | Create | Empty page stub for Phase 6E |
| `src/renderer/App.tsx` | Modify | Replace health check with ThemeProvider + Router + AppShell |
| `src/renderer/main.tsx` | Modify | (No changes needed — App handles everything) |
| `tests/renderer/setup.ts` | Modify | Add @testing-library/user-event setup |
| `tests/renderer/Button.test.tsx` | Create | Button component tests |
| `tests/renderer/Input.test.tsx` | Create | Input component tests |
| `tests/renderer/Card.test.tsx` | Create | Card component tests |
| `tests/renderer/Sidebar.test.tsx` | Create | Sidebar navigation tests |
| `tests/renderer/SearchBar.test.tsx` | Create | SearchBar component tests |
| `tests/renderer/AppShell.test.tsx` | Create | AppShell layout + routing integration tests |
| `tests/renderer/App.test.tsx` | Modify | Update to test new shell (router + theme + sidebar) |
| `index.html` | Modify | Add Google Fonts + Material Symbols preconnect links |

---

## Task 1: Install dependencies and configure build tools

**Files:**
- Modify: `package.json`
- Create: `postcss.config.js`

- [ ] **Step 1: Install react-router-dom and @testing-library/user-event**

```bash
cd /Users/oscarpurtell/claudeCode/studyBot/StudyBot
npm install react-router-dom
npm install -D @testing-library/user-event
```

Expected: `react-router-dom` added to `dependencies`, `@testing-library/user-event` added to `devDependencies`.

- [ ] **Step 2: Verify package.json has the new dependency**

Read `package.json` and confirm `react-router-dom` appears in `"dependencies"`.

- [ ] **Step 3: Create postcss.config.js**

Create `postcss.config.js`:
```js
module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

- [ ] **Step 4: Commit**

```bash
git add package.json package-lock.json postcss.config.js
git commit -m "chore: add react-router-dom, user-event, and postcss config for Phase 5"
```

---

## Task 2: Design system tokens — Tailwind config + CSS custom properties

This is the foundation. Every subsequent component references these tokens.

**Files:**
- Modify: `tailwind.config.js`
- Modify: `src/renderer/styles/global.css`

- [ ] **Step 1: Replace tailwind.config.js with full Archival Protocol tokens**

Replace the entire contents of `tailwind.config.js`:

```js
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./index.html", "./src/renderer/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        headline: ["Newsreader", "Georgia", "serif"],
        body: ["Space Grotesk", "system-ui", "sans-serif"],
        label: ["Space Grotesk", "system-ui", "sans-serif"],
        mono: ["IBM Plex Mono", "Menlo", "monospace"],
      },
      fontSize: {
        "display-lg": [
          "3.5rem",
          { lineHeight: "1.1", letterSpacing: "-0.02em", fontWeight: "700" },
        ],
        "headline-md": [
          "1.75rem",
          { lineHeight: "1.3", letterSpacing: "-0.01em", fontWeight: "600" },
        ],
        "title-lg": [
          "1.375rem",
          { lineHeight: "1.4", fontWeight: "500" },
        ],
        "body-md": [
          "0.875rem",
          { lineHeight: "1.6" },
        ],
        "label-sm": [
          "0.6875rem",
          {
            lineHeight: "1.4",
            letterSpacing: "0.08em",
            textTransform: "uppercase",
          },
        ],
      },
      colors: {
        // Surface hierarchy
        surface: "var(--color-surface)",
        "surface-dim": "var(--color-surface-dim)",
        "surface-bright": "var(--color-surface-bright)",
        "surface-container-lowest": "var(--color-surface-container-lowest)",
        "surface-container-low": "var(--color-surface-container-low)",
        "surface-container": "var(--color-surface-container)",
        "surface-container-high": "var(--color-surface-container-high)",
        "surface-container-highest": "var(--color-surface-container-highest)",
        // Content
        "on-surface": "var(--color-on-surface)",
        "on-surface-variant": "var(--color-on-surface-variant)",
        // Primary
        primary: "var(--color-primary)",
        "on-primary": "var(--color-on-primary)",
        "primary-container": "var(--color-primary-container)",
        "on-primary-container": "var(--color-on-primary-container)",
        "primary-fixed": "var(--color-primary-fixed)",
        "primary-fixed-dim": "var(--color-primary-fixed-dim)",
        "on-primary-fixed": "var(--color-on-primary-fixed)",
        "on-primary-fixed-variant": "var(--color-on-primary-fixed-variant)",
        // Secondary
        secondary: "var(--color-secondary)",
        "on-secondary": "var(--color-on-secondary)",
        "secondary-container": "var(--color-secondary-container)",
        "on-secondary-container": "var(--color-on-secondary-container)",
        "secondary-fixed": "var(--color-secondary-fixed)",
        "secondary-fixed-dim": "var(--color-secondary-fixed-dim)",
        "on-secondary-fixed": "var(--color-on-secondary-fixed)",
        "on-secondary-fixed-variant": "var(--color-on-secondary-fixed-variant)",
        // Tertiary (highlighter accent)
        tertiary: "var(--color-tertiary)",
        "on-tertiary": "var(--color-on-tertiary)",
        "tertiary-container": "var(--color-tertiary-container)",
        "on-tertiary-container": "var(--color-on-tertiary-container)",
        "tertiary-fixed": "var(--color-tertiary-fixed)",
        "tertiary-fixed-dim": "var(--color-tertiary-fixed-dim)",
        "on-tertiary-fixed": "var(--color-on-tertiary-fixed)",
        "on-tertiary-fixed-variant": "var(--color-on-tertiary-fixed-variant)",
        // Error
        error: "var(--color-error)",
        "on-error": "var(--color-on-error)",
        "error-container": "var(--color-error-container)",
        "on-error-container": "var(--color-on-error-container)",
        // Utility
        outline: "var(--color-outline)",
        "outline-variant": "var(--color-outline-variant)",
        "surface-variant": "var(--color-surface-variant)",
        "inverse-surface": "var(--color-inverse-surface)",
        "inverse-on-surface": "var(--color-inverse-on-surface)",
        "inverse-primary": "var(--color-inverse-primary)",
        "surface-tint": "var(--color-surface-tint)",
        background: "var(--color-background)",
        "on-background": "var(--color-on-background)",
        // Status colours for mastery levels
        status: {
          success: "#10b981",
          caution: "#fbbf24",
          critical: "#f87171",
        },
      },
      borderRadius: {
        DEFAULT: "0.125rem",
        lg: "0.25rem",
        xl: "0.5rem",
        full: "0.75rem",
      },
      boxShadow: {
        ambient:
          "0 12px 40px rgba(27, 28, 24, 0.06)",
      },
      backdropBlur: {
        archival: "12px",
      },
    },
  },
  plugins: [],
};
```

- [ ] **Step 2: Replace global.css with full design system styles**

Replace the entire contents of `src/renderer/styles/global.css`:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

/* ============================================================
   THE ARCHIVAL PROTOCOL — Design System Tokens
   CSS custom properties for light + dark themes.
   ============================================================ */

@layer base {
  :root {
    /* Surface hierarchy */
    --color-background: #fbf9f3;
    --color-surface: #fbf9f3;
    --color-surface-dim: #dcdad4;
    --color-surface-bright: #fbf9f3;
    --color-surface-container-lowest: #ffffff;
    --color-surface-container-low: #f5f3ed;
    --color-surface-container: #f0eee8;
    --color-surface-container-high: #eae8e2;
    --color-surface-container-highest: #e4e2dd;

    /* Content */
    --color-on-background: #1b1c18;
    --color-on-surface: #1b1c18;
    --color-on-surface-variant: #404847;
    --color-surface-variant: #e4e2dd;

    /* Primary — archival ink teal */
    --color-primary: #2d5a54;
    --color-on-primary: #ffffff;
    --color-primary-container: #2d5a54;
    --color-on-primary-container: #a1cfc8;
    --color-primary-fixed: #bcece4;
    --color-primary-fixed-dim: #a1d0c8;
    --color-on-primary-fixed: #00201d;
    --color-on-primary-fixed-variant: #204e48;

    /* Secondary */
    --color-secondary: #4a6267;
    --color-on-secondary: #ffffff;
    --color-secondary-container: #cde7ed;
    --color-on-secondary-container: #50686d;
    --color-secondary-fixed: #cde7ed;
    --color-secondary-fixed-dim: #b1cbd1;
    --color-on-secondary-fixed: #051f23;
    --color-on-secondary-fixed-variant: #334b4f;

    /* Tertiary — highlighter accent */
    --color-tertiary: #3a3f00;
    --color-on-tertiary: #ffffff;
    --color-tertiary-container: #505700;
    --color-on-tertiary-container: #c2cf47;
    --color-tertiary-fixed: #dae058;
    --color-tertiary-fixed-dim: #c2cf47;
    --color-on-tertiary-fixed: #1a1d00;
    --color-on-tertiary-fixed-variant: #444b00;

    /* Error */
    --color-error: #ba1a1a;
    --color-on-error: #ffffff;
    --color-error-container: #ffdad6;
    --color-on-error-container: #93000a;

    /* Utility */
    --color-outline: #707977;
    --color-outline-variant: #c0c8c6;
    --color-inverse-surface: #30312d;
    --color-inverse-on-surface: #f3f1eb;
    --color-inverse-primary: #a1d0c8;
    --color-surface-tint: #396660;
  }

  /* Dark theme overrides */
  .dark {
    --color-background: #131411;
    --color-surface: #131411;
    --color-surface-dim: #131411;
    --color-surface-bright: #393a36;
    --color-surface-container-lowest: #0e0f0c;
    --color-surface-container-low: #1b1c18;
    --color-surface-container: #1f201c;
    --color-surface-container-high: #2a2b27;
    --color-surface-container-highest: #343531;

    --color-on-background: #e4e2dd;
    --color-on-surface: #e4e2dd;
    --color-on-surface-variant: #c0c8c6;
    --color-surface-variant: #404847;

    --color-primary: #a1d0c8;
    --color-on-primary: #003732;
    --color-primary-container: #13423d;
    --color-on-primary-container: #bcece4;
    --color-primary-fixed: #bcece4;
    --color-primary-fixed-dim: #a1d0c8;
    --color-on-primary-fixed: #00201d;
    --color-on-primary-fixed-variant: #204e48;

    --color-secondary: #b1cbd1;
    --color-on-secondary: #1c3438;
    --color-secondary-container: #334b4f;
    --color-on-secondary-container: #cde7ed;
    --color-secondary-fixed: #cde7ed;
    --color-secondary-fixed-dim: #b1cbd1;
    --color-on-secondary-fixed: #051f23;
    --color-on-secondary-fixed-variant: #334b4f;

    --color-tertiary: #c2cf47;
    --color-on-tertiary: #2d3200;
    --color-tertiary-container: #444b00;
    --color-on-tertiary-container: #dfec60;
    --color-tertiary-fixed: #dae058;
    --color-tertiary-fixed-dim: #c2cf47;
    --color-on-tertiary-fixed: #1a1d00;
    --color-on-tertiary-fixed-variant: #444b00;

    --color-error: #ffb4ab;
    --color-on-error: #690005;
    --color-error-container: #93000a;
    --color-on-error-container: #ffdad6;

    --color-outline: #8a9390;
    --color-outline-variant: #404847;
    --color-inverse-surface: #e4e2dd;
    --color-inverse-on-surface: #1b1c18;
    --color-inverse-primary: #2d5a54;
    --color-surface-tint: #a1d0c8;
  }
}

/* ============================================================
   Base styles
   ============================================================ */

@layer base {
  html {
    font-family: "Space Grotesk", system-ui, sans-serif;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }

  body {
    @apply bg-background text-on-surface;
  }

  /* Text selection uses highlighter accent */
  ::selection {
    background-color: var(--color-tertiary-fixed);
    color: var(--color-on-tertiary-fixed);
  }
}

/* ============================================================
   Dot-grid background pattern
   ============================================================ */

.dot-grid {
  background-image: radial-gradient(circle, var(--color-outline) 1px, transparent 1px);
  background-size: 24px 24px;
  opacity: 0.03;
  pointer-events: none;
}

.dark .dot-grid {
  opacity: 0.06;
}

/* ============================================================
   Marginalia — vertical side notes
   ============================================================ */

.marginalia {
  writing-mode: vertical-rl;
  transform: rotate(180deg);
}

/* ============================================================
   Ruled-paper texture (for quiz answer input)
   ============================================================ */

.ruled-paper {
  background-image: linear-gradient(var(--color-outline-variant) 1px, transparent 1px);
  background-size: 100% 2.5rem;
  line-height: 2.5rem;
}

/* ============================================================
   Scrollbar — minimal, archival style
   ============================================================ */

@layer base {
  ::-webkit-scrollbar {
    width: 6px;
  }

  ::-webkit-scrollbar-track {
    background: transparent;
  }

  ::-webkit-scrollbar-thumb {
    background: var(--color-outline-variant);
    border-radius: 3px;
  }

  ::-webkit-scrollbar-thumb:hover {
    background: var(--color-outline);
  }
}
```

- [ ] **Step 3: Update index.html to load Google Fonts and Material Symbols**

Replace the entire contents of `index.html`:

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Clinical Recall Assistant</title>
    <!-- Preconnect to Google Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <!-- Load fonts: Newsreader (serif), Space Grotesk (sans), IBM Plex Mono -->
    <link
      href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,200..800;1,6..72,200..800&family=Space+Grotesk:wght@300..700&family=IBM+Plex+Mono:wght@400;500&display=swap"
      rel="stylesheet"
    />
    <!-- Material Symbols for icons -->
    <link
      href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap"
      rel="stylesheet"
    />
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/renderer/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 4: Verify Tailwind compiles without errors**

```bash
npx tailwindcss --content "./src/renderer/styles/global.css" --help
```

Expected: no errors. Then run:

```bash
npm run test
```

Expected: existing tests still pass (App.test.tsx tests the old health check — they will fail in the next task, that's expected).

- [ ] **Step 5: Commit**

```bash
git add tailwind.config.js src/renderer/styles/global.css index.html
git commit -m "feat: implement Archival Protocol design tokens with light/dark theme"
```

---

## Task 3: Theme system — ThemeProvider and useTheme hook

**Files:**
- Create: `src/renderer/hooks/useTheme.tsx`

- [ ] **Step 1: Write the ThemeProvider and useTheme hook**

Create `src/renderer/hooks/useTheme.tsx`:

```tsx
import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

type Theme = "light" | "dark";

interface ThemeContextValue {
  theme: Theme;
  toggleTheme: () => void;
  setTheme: (theme: Theme) => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

const STORAGE_KEY = "studybot-theme";

function getInitialTheme(): Theme {
  if (typeof window === "undefined") return "light";
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === "dark" || stored === "light") return stored;
  // Respect system preference on first visit
  if (window.matchMedia("(prefers-color-scheme: dark)").matches) return "dark";
  return "light";
}

function applyTheme(theme: Theme) {
  const root = document.documentElement;
  if (theme === "dark") {
    root.classList.add("dark");
  } else {
    root.classList.remove("dark");
  }
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(getInitialTheme);

  useEffect(() => {
    applyTheme(theme);
    localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  const toggleTheme = () => {
    setThemeState((prev) => (prev === "light" ? "dark" : "light"));
  };

  const setTheme = (t: Theme) => {
    setThemeState(t);
  };

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return ctx;
}
```

- [ ] **Step 2: Commit**

```bash
git add src/renderer/hooks/useTheme.tsx
git commit -m "feat: add ThemeProvider context with dark mode toggle"
```

---

## Task 4: Button component — TDD

**Files:**
- Create: `src/renderer/components/Button.tsx`
- Create: `tests/renderer/Button.test.tsx`

- [ ] **Step 1: Write the failing tests**

Create `tests/renderer/Button.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import Button from "../../src/renderer/components/Button";

describe("Button", () => {
  it("renders children text", () => {
    render(<Button>Start Session</Button>);
    expect(screen.getByRole("button", { name: "Start Session" })).toBeInTheDocument();
  });

  it("calls onClick when clicked", async () => {
    const handleClick = vi.fn();
    render(<Button onClick={handleClick}>Click</Button>);
    await userEvent.click(screen.getByRole("button"));
    expect(handleClick).toHaveBeenCalledOnce();
  });

  it('applies primary variant styles by default', () => {
    render(<Button>Primary</Button>);
    const btn = screen.getByRole("button");
    expect(btn.className).toContain("bg-primary");
    expect(btn.className).toContain("text-on-primary");
  });

  it('applies secondary variant styles', () => {
    render(<Button variant="secondary">Secondary</Button>);
    const btn = screen.getByRole("button");
    expect(btn.className).toContain("bg-surface-container-high");
    expect(btn.className).toContain("text-on-surface");
  });

  it('applies tertiary variant styles', () => {
    render(<Button variant="tertiary">Tertiary</Button>);
    const btn = screen.getByRole("button");
    expect(btn.className).toContain("text-primary");
    // Tertiary has no filled background
    expect(btn.className).not.toContain("bg-primary");
  });

  it('is disabled when disabled prop is true', () => {
    render(<Button disabled>Disabled</Button>);
    expect(screen.getByRole("button")).toBeDisabled();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test -- tests/renderer/Button.test.tsx`
Expected: FAIL — module not found

- [ ] **Step 3: Implement Button component**

Create `src/renderer/components/Button.tsx`:

```tsx
import { type ButtonHTMLAttributes, type ReactNode } from "react";

type ButtonVariant = "primary" | "secondary" | "tertiary";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  children: ReactNode;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    "bg-primary text-on-primary hover:opacity-90 active:opacity-80",
  secondary:
    "bg-surface-container-high text-on-surface hover:bg-surface-container-highest active:bg-surface-container",
  tertiary:
    "bg-transparent text-primary hover:bg-tertiary-fixed/20 active:bg-tertiary-fixed/10",
};

export default function Button({
  variant = "primary",
  children,
  className = "",
  disabled,
  ...rest
}: ButtonProps) {
  return (
    <button
      className={`
        inline-flex items-center gap-2
        font-label text-label-sm uppercase tracking-wider
        py-3 px-6 rounded transition-all duration-200
        disabled:opacity-40 disabled:cursor-not-allowed
        ${variantClasses[variant]}
        ${className}
      `}
      disabled={disabled}
      {...rest}
    >
      {children}
    </button>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- tests/renderer/Button.test.tsx`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/renderer/components/Button.tsx tests/renderer/Button.test.tsx
git commit -m "feat: add Button component with primary, secondary, tertiary variants"
```

---

## Task 5: Input and SearchBar components — TDD

**Files:**
- Create: `src/renderer/components/Input.tsx`
- Create: `src/renderer/components/SearchBar.tsx`
- Create: `tests/renderer/Input.test.tsx`
- Create: `tests/renderer/SearchBar.test.tsx`

- [ ] **Step 1: Write the failing Input tests**

Create `tests/renderer/Input.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import Input from "../../src/renderer/components/Input";

describe("Input", () => {
  it("renders with placeholder text", () => {
    render(<Input placeholder="Enter answer..." />);
    expect(screen.getByPlaceholderText("Enter answer...")).toBeInTheDocument();
  });

  it("renders with a label", () => {
    render(<Input label="Clinical Notes" />);
    expect(screen.getByLabelText("Clinical Notes")).toBeInTheDocument();
  });

  it("accepts typed input", async () => {
    render(<Input placeholder="Type here" />);
    const input = screen.getByPlaceholderText("Type here");
    await userEvent.type(input, "adrenaline 1mg");
    expect(input).toHaveValue("adrenaline 1mg");
  });

  it("calls onChange when value changes", async () => {
    const handleChange = vi.fn();
    render(<Input placeholder="Test" onChange={handleChange} />);
    await userEvent.type(screen.getByPlaceholderText("Test"), "a");
    expect(handleChange).toHaveBeenCalled();
  });

  it("is disabled when disabled prop is true", () => {
    render(<Input placeholder="Disabled" disabled />);
    expect(screen.getByPlaceholderText("Disabled")).toBeDisabled();
  });
});
```

- [ ] **Step 2: Write the failing SearchBar tests**

Create `tests/renderer/SearchBar.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import SearchBar from "../../src/renderer/components/SearchBar";

describe("SearchBar", () => {
  it("renders with search placeholder", () => {
    render(<SearchBar />);
    expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument();
  });

  it("renders with custom placeholder", () => {
    render(<SearchBar placeholder="Search guidelines..." />);
    expect(screen.getByPlaceholderText("Search guidelines...")).toBeInTheDocument();
  });

  it("displays a search icon", () => {
    render(<SearchBar />);
    // Material Symbols icon with text "search"
    expect(screen.getByText("search")).toBeInTheDocument();
  });

  it("calls onSearch when Enter is pressed", async () => {
    const handleSearch = vi.fn();
    render(<SearchBar onSearch={handleSearch} />);
    const input = screen.getByPlaceholderText(/search/i);
    await userEvent.type(input, "cardiac arrest{Enter}");
    expect(handleSearch).toHaveBeenCalledWith("cardiac arrest");
  });
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `npm test -- tests/renderer/Input.test.tsx tests/renderer/SearchBar.test.tsx`
Expected: FAIL — modules not found

- [ ] **Step 4: Implement Input component**

Create `src/renderer/components/Input.tsx`:

```tsx
import { type InputHTMLAttributes, useId } from "react";

interface InputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "style"> {
  label?: string;
}

export default function Input({ label, className = "", id, ...rest }: InputProps) {
  const autoId = useId();
  const inputId = id || autoId;

  return (
    <div className="flex flex-col gap-1">
      {label && (
        <label
          htmlFor={inputId}
          className="font-label text-label-sm text-on-surface-variant uppercase tracking-wider"
        >
          {label}
        </label>
      )}
      <input
        id={inputId}
        className={`
          w-full
          bg-transparent
          border-0 border-b border-outline-variant/20
          text-on-surface font-body text-body-md
          py-2 px-0
          transition-all duration-200
          focus:border-primary focus:bg-surface-container-lowest/50
          focus:outline-none
          placeholder:text-on-surface-variant/40
          disabled:opacity-40 disabled:cursor-not-allowed
          ${className}
        `}
        {...rest}
      />
    </div>
  );
}
```

- [ ] **Step 5: Implement SearchBar component**

Create `src/renderer/components/SearchBar.tsx`:

```tsx
import { useState, type KeyboardEvent } from "react";

interface SearchBarProps {
  placeholder?: string;
  onSearch?: (query: string) => void;
  className?: string;
}

export default function SearchBar({
  placeholder = "Search the archive...",
  onSearch,
  className = "",
}: SearchBarProps) {
  const [query, setQuery] = useState("");

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && onSearch) {
      onSearch(query.trim());
    }
  };

  return (
    <div
      className={`
        flex items-center gap-3
        bg-surface-container-low
        px-4 py-3
        ${className}
      `}
    >
      <span className="material-symbols-outlined text-on-surface-variant text-xl select-none">
        search
      </span>
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        className="
          w-full bg-transparent
          text-on-surface font-body text-body-md
          placeholder:text-on-surface-variant/40
          focus:outline-none
        "
      />
    </div>
  );
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `npm test -- tests/renderer/Input.test.tsx tests/renderer/SearchBar.test.tsx`
Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add src/renderer/components/Input.tsx src/renderer/components/SearchBar.tsx tests/renderer/Input.test.tsx tests/renderer/SearchBar.test.tsx
git commit -m "feat: add Input (field-note style) and SearchBar components"
```

---

## Task 6: Card and Tag components — TDD

**Files:**
- Create: `src/renderer/components/Card.tsx`
- Create: `src/renderer/components/Tag.tsx`
- Create: `tests/renderer/Card.test.tsx`

- [ ] **Step 1: Write the failing Card tests**

Create `tests/renderer/Card.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import Card from "../../src/renderer/components/Card";

describe("Card", () => {
  it("renders children", () => {
    render(<Card>Card content</Card>);
    expect(screen.getByText("Card content")).toBeInTheDocument();
  });

  it("calls onClick when clicked", async () => {
    const handleClick = vi.fn();
    render(<Card onClick={handleClick}>Clickable</Card>);
    await userEvent.click(screen.getByText("Clickable"));
    expect(handleClick).toHaveBeenCalledOnce();
  });

  it("applies hover-to-lowest effect when interactive", () => {
    render(<Card onClick={() => {}}>Interactive</Card>);
    const card = screen.getByText("Interactive").closest("div");
    expect(card?.className).toContain("hover:bg-surface-container-lowest");
  });

  it("does not apply hover effect when non-interactive", () => {
    render(<Card>Static</Card>);
    const card = screen.getByText("Static").closest("div");
    expect(card?.className).not.toContain("hover:bg-surface-container-lowest");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test -- tests/renderer/Card.test.tsx`
Expected: FAIL — module not found

- [ ] **Step 3: Implement Card component**

Create `src/renderer/components/Card.tsx`:

```tsx
import type { ReactNode, HTMLAttributes } from "react";

interface CardProps extends Omit<HTMLAttributes<HTMLDivElement>, "style"> {
  children: ReactNode;
  onClick?: () => void;
  className?: string;
}

export default function Card({
  children,
  onClick,
  className = "",
  ...rest
}: CardProps) {
  const interactive = typeof onClick === "function";

  return (
    <div
      role={interactive ? "button" : undefined}
      tabIndex={interactive ? 0 : undefined}
      onClick={onClick}
      onKeyDown={
        interactive
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onClick();
              }
            }
          : undefined
      }
      className={`
        bg-surface-container-low p-6
        ${interactive ? "hover:bg-surface-container-lowest cursor-pointer" : ""}
        transition-colors duration-200
        ${className}
      `}
      {...rest}
    >
      {children}
    </div>
  );
}
```

- [ ] **Step 4: Implement Tag component**

Create `src/renderer/components/Tag.tsx`:

```tsx
import type { ReactNode } from "react";

interface TagProps {
  children: ReactNode;
  className?: string;
}

export default function Tag({ children, className = "" }: TagProps) {
  return (
    <span
      className={`
        inline-block px-2 py-1
        bg-surface-container-highest
        font-label text-[9px] uppercase tracking-widest
        text-on-surface-variant
        ${className}
      `}
    >
      {children}
    </span>
  );
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `npm test -- tests/renderer/Card.test.tsx`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add src/renderer/components/Card.tsx src/renderer/components/Tag.tsx tests/renderer/Card.test.tsx
git commit -m "feat: add Card (document-stack style) and Tag components"
```

---

## Task 7: MasteryIndicator component

**Files:**
- Create: `src/renderer/components/MasteryIndicator.tsx`

This is a small display component used by the knowledge heatmap cards. Not complex enough for dedicated tests — covered by integration tests in Phase 6.

- [ ] **Step 1: Implement MasteryIndicator**

Create `src/renderer/components/MasteryIndicator.tsx`:

```tsx
interface MasteryIndicatorProps {
  percentage: number;
  label?: string;
}

function getStatusColour(percentage: number): string {
  if (percentage >= 85) return "bg-status-success";
  if (percentage >= 60) return "bg-status-caution";
  return "bg-status-critical";
}

function getGlowColour(percentage: number): string {
  if (percentage >= 85) return "shadow-[0_0_8px_rgba(16,185,129,0.4)]";
  if (percentage >= 60) return "";
  return "";
}

export default function MasteryIndicator({
  percentage,
  label,
}: MasteryIndicatorProps) {
  const clamped = Math.max(0, Math.min(100, percentage));
  const statusColour = getStatusColour(clamped);
  const glowColour = getGlowColour(clamped);

  return (
    <div className="space-y-1">
      {label && (
        <p className="font-label text-label-sm text-on-surface-variant">
          {label}
        </p>
      )}
      {/* Status dot */}
      <div className="flex items-center gap-2">
        <div
          className={`w-2 h-2 rounded-full ${statusColour} ${glowColour}`}
        />
        <span className="font-label text-label-sm text-on-surface-variant">
          {clamped}% Mastery
        </span>
      </div>
      {/* Progress bar */}
      <div className="h-1 w-full bg-outline-variant/20">
        <div
          className={`h-full ${statusColour} transition-all duration-500`}
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add src/renderer/components/MasteryIndicator.tsx
git commit -m "feat: add MasteryIndicator component for heatmap cards"
```

---

## Task 8: Sidebar navigation component — TDD

**Files:**
- Create: `src/renderer/components/Sidebar.tsx`
- Create: `tests/renderer/Sidebar.test.tsx`

- [ ] **Step 1: Write the failing tests**

Create `tests/renderer/Sidebar.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { MemoryRouter } from "react-router-dom";
import Sidebar from "../../src/renderer/components/Sidebar";

// The Sidebar needs a router context to render <Link> elements
function renderWithRouter(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

describe("Sidebar", () => {
  it("renders the app title", () => {
    renderWithRouter(<Sidebar />);
    expect(screen.getByText("Clinical Registry")).toBeInTheDocument();
  });

  it("renders the version label", () => {
    renderWithRouter(<Sidebar />);
    expect(screen.getByText(/Archival Protocol/i)).toBeInTheDocument();
  });

  it("renders all primary navigation items", () => {
    renderWithRouter(<Sidebar />);
    expect(screen.getByText("Observations")).toBeInTheDocument();
    expect(screen.getByText("Clinical Protocols")).toBeInTheDocument();
    expect(screen.getByText("Research Notes")).toBeInTheDocument();
    expect(screen.getByText("Medication Ledger")).toBeInTheDocument();
  });

  it("renders the settings link", () => {
    renderWithRouter(<Sidebar />);
    expect(screen.getByText("Curator Settings")).toBeInTheDocument();
  });

  it("renders the Start Session button", () => {
    renderWithRouter(<Sidebar />);
    expect(screen.getByRole("button", { name: /new documentation/i })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test -- tests/renderer/Sidebar.test.tsx`
Expected: FAIL — module not found

- [ ] **Step 3: Implement Sidebar component**

Create `src/renderer/components/Sidebar.tsx`:

```tsx
import { NavLink, useNavigate } from "react-router-dom";
import { useTheme } from "../hooks/useTheme";

interface NavItem {
  icon: string;
  label: string;
  path: string;
}

const primaryNav: NavItem[] = [
  { icon: "visibility", label: "Observations", path: "/" },
  { icon: "clinical_notes", label: "Clinical Protocols", path: "/quiz" },
  { icon: "biotech", label: "Research Notes", path: "/library" },
  { icon: "medication", label: "Medication Ledger", path: "/medication" },
];

const secondaryNav: NavItem[] = [
  { icon: "settings", label: "Curator Settings", path: "/settings" },
];

export default function Sidebar() {
  const navigate = useNavigate();
  const { theme, toggleTheme } = useTheme();

  return (
    <aside className="h-screen w-64 fixed left-0 top-0 bg-surface-container-low flex flex-col py-8 z-40">
      {/* App title */}
      <div className="px-6 mb-12">
        <h1 className="font-headline text-2xl font-bold text-primary leading-tight">
          Clinical Registry
        </h1>
        <p className="font-label text-[10px] uppercase tracking-[0.2em] text-on-surface-variant mt-1">
          Archival Protocol v1.0
        </p>
      </div>

      {/* Primary navigation */}
      <nav className="flex-1 space-y-2 px-4">
        {primaryNav.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path === "/"}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-3 transition-all duration-200 ${
                isActive
                  ? "bg-surface-container-lowest text-primary font-bold"
                  : "text-on-surface-variant hover:text-primary hover:bg-tertiary-fixed/20"
              }`
            }
          >
            <span className="material-symbols-outlined">{item.icon}</span>
            <span className="font-label text-sm uppercase tracking-wider">
              {item.label}
            </span>
          </NavLink>
        ))}
      </nav>

      {/* Bottom section */}
      <div className="px-4 mt-auto space-y-6">
        {/* Start Session CTA */}
        <button
          onClick={() => navigate("/quiz")}
          className="w-full bg-primary text-on-primary py-4 px-4 font-label text-xs uppercase tracking-[0.2em] hover:opacity-90 transition-opacity"
        >
          New Documentation
        </button>

        {/* Theme toggle */}
        <button
          onClick={toggleTheme}
          className="flex items-center gap-3 px-4 w-full text-on-surface-variant hover:text-primary transition-colors"
        >
          <span className="material-symbols-outlined text-sm">
            {theme === "dark" ? "light_mode" : "dark_mode"}
          </span>
          <span className="font-label text-xs uppercase tracking-wider">
            {theme === "dark" ? "Light Mode" : "Dark Mode"}
          </span>
        </button>

        {/* Secondary nav */}
        <div className="space-y-3 pt-6 border-t border-outline-variant/20">
          {secondaryNav.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 font-label text-xs uppercase tracking-wider transition-colors ${
                  isActive
                    ? "text-primary"
                    : "text-on-surface-variant hover:text-primary"
                }`
              }
            >
              <span className="material-symbols-outlined text-sm">
                {item.icon}
              </span>
              {item.label}
            </NavLink>
          ))}
        </div>
      </div>
    </aside>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- tests/renderer/Sidebar.test.tsx`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/renderer/components/Sidebar.tsx tests/renderer/Sidebar.test.tsx
git commit -m "feat: add Sidebar navigation with active states and dark mode toggle"
```

---

## Task 9: AppShell layout + page stubs + Router — TDD

**Files:**
- Create: `src/renderer/components/AppShell.tsx`
- Create: `src/renderer/pages/Dashboard.tsx`
- Create: `src/renderer/pages/Quiz.tsx`
- Create: `src/renderer/pages/Feedback.tsx`
- Create: `src/renderer/pages/Library.tsx`
- Create: `src/renderer/pages/Settings.tsx`
- Create: `tests/renderer/AppShell.test.tsx`

- [ ] **Step 1: Write the failing AppShell tests**

Create `tests/renderer/AppShell.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { MemoryRouter } from "react-router-dom";
import AppShell from "../../src/renderer/components/AppShell";

function renderWithRouter(route = "/") {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <AppShell />
    </MemoryRouter>
  );
}

describe("AppShell", () => {
  it("renders the sidebar", () => {
    renderWithRouter();
    expect(screen.getByText("Clinical Registry")).toBeInTheDocument();
  });

  it("renders the search bar", () => {
    renderWithRouter();
    expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument();
  });

  it("renders the dot-grid background", () => {
    const { container } = renderWithRouter();
    expect(container.querySelector(".dot-grid")).toBeInTheDocument();
  });

  it("renders dashboard content at root route", () => {
    renderWithRouter("/");
    // Dashboard stub should render something
    expect(screen.getByText(/dashboard/i)).toBeInTheDocument();
  });

  it("renders quiz content at /quiz route", () => {
    renderWithRouter("/quiz");
    expect(screen.getByText(/quiz/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test -- tests/renderer/AppShell.test.tsx`
Expected: FAIL — module not found

- [ ] **Step 3: Create page stub components**

Create `src/renderer/pages/Dashboard.tsx`:
```tsx
export default function Dashboard() {
  return (
    <div>
      <h2 className="font-headline text-display-lg text-primary">
        Clinical Knowledge Repository
      </h2>
      <p className="font-body text-body-md text-on-surface-variant mt-2">
        Dashboard placeholder — Phase 6A will implement knowledge heatmap,
        performance metrics, and recent archival entries.
      </p>
    </div>
  );
}
```

Create `src/renderer/pages/Quiz.tsx`:
```tsx
export default function Quiz() {
  return (
    <div>
      <h2 className="font-headline text-display-lg text-primary">
        Active Recall Protocol
      </h2>
      <p className="font-body text-body-md text-on-surface-variant mt-2">
        Quiz placeholder — Phase 6B will implement question display,
        answer input, timer, and progress tracking.
      </p>
    </div>
  );
}
```

Create `src/renderer/pages/Feedback.tsx`:
```tsx
export default function Feedback() {
  return (
    <div>
      <h2 className="font-headline text-display-lg text-primary">
        Feedback Evaluation
      </h2>
      <p className="font-body text-body-md text-on-surface-variant mt-2">
        Feedback placeholder — Phase 6C will implement the split-view
        analysis panel with source citations.
      </p>
    </div>
  );
}
```

Create `src/renderer/pages/Library.tsx`:
```tsx
export default function Library() {
  return (
    <div>
      <h2 className="font-headline text-display-lg text-primary">
        Research Notes
      </h2>
      <p className="font-body text-body-md text-on-surface-variant mt-2">
        Library placeholder — Phase 6D will implement the source repository,
        sync status, and cleaning feed.
      </p>
    </div>
  );
}
```

Create `src/renderer/pages/Settings.tsx`:
```tsx
export default function Settings() {
  return (
    <div>
      <h2 className="font-headline text-display-lg text-primary">
        Curator Settings
      </h2>
      <p className="font-body text-body-md text-on-surface-variant mt-2">
        Settings placeholder — Phase 6E will implement quiz blacklist,
        model selection, API keys, and data management.
      </p>
    </div>
  );
}
```

- [ ] **Step 4: Implement AppShell component**

Create `src/renderer/components/AppShell.tsx`:

```tsx
import { Routes, Route } from "react-router-dom";
import Sidebar from "./Sidebar";
import SearchBar from "./SearchBar";
import Dashboard from "../pages/Dashboard";
import Quiz from "../pages/Quiz";
import Feedback from "../pages/Feedback";
import Library from "../pages/Library";
import Settings from "../pages/Settings";

export default function AppShell() {
  return (
    <>
      {/* Dot-grid background texture */}
      <div className="fixed inset-0 dot-grid" />

      {/* Sidebar navigation */}
      <Sidebar />

      {/* Main content area */}
      <main className="ml-64 min-h-screen p-8 lg:p-12 max-w-7xl relative z-10">
        {/* Universal search bar */}
        <div className="mb-8">
          <SearchBar placeholder="Search the archive..." />
        </div>

        {/* Page routes */}
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/quiz" element={<Quiz />} />
          <Route path="/feedback" element={<Feedback />} />
          <Route path="/library" element={<Library />} />
          <Route path="/medication" element={<Dashboard />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>

        {/* System footer */}
        <footer className="mt-24 pt-8 border-t border-outline-variant/10 flex justify-between items-center">
          <div className="flex items-center gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-status-success" />
            <span className="font-mono text-[10px] text-on-surface-variant">
              Archival System Active
            </span>
          </div>
          <span className="font-headline italic text-on-surface-variant/40 text-sm">
            Precision is the only permissible outcome.
          </span>
        </footer>
      </main>
    </>
  );
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `npm test -- tests/renderer/AppShell.test.tsx`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add src/renderer/components/AppShell.tsx src/renderer/pages/ tests/renderer/AppShell.test.tsx
git commit -m "feat: add AppShell layout with router, sidebar, search, and page stubs"
```

---

## Task 10: Update App.tsx to wire everything together

**Files:**
- Modify: `src/renderer/App.tsx`
- Modify: `tests/renderer/App.test.tsx`

- [ ] **Step 1: Replace App.tsx with shell wrapper**

Replace the entire contents of `src/renderer/App.tsx`:

```tsx
import { BrowserRouter } from "react-router-dom";
import { ThemeProvider } from "./hooks/useTheme";
import AppShell from "./components/AppShell";

export default function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <AppShell />
      </BrowserRouter>
    </ThemeProvider>
  );
}
```

- [ ] **Step 2: Update App tests for the new shell**

Replace the entire contents of `tests/renderer/App.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import App from "../../src/renderer/App";

// Mock the health endpoint fetch — App no longer does health checks,
// but we mock it to prevent network errors in test env
beforeAll(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({ status: "ok" }),
    })
  );
});

describe("App", () => {
  it("renders the sidebar with app title", () => {
    render(<App />);
    expect(screen.getByText("Clinical Registry")).toBeInTheDocument();
  });

  it("renders the search bar", () => {
    render(<App />);
    expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument();
  });

  it("renders the dashboard as default page", () => {
    render(<App />);
    expect(screen.getByText(/Clinical Knowledge Repository/i)).toBeInTheDocument();
  });

  it("renders the theme toggle", () => {
    render(<App />);
    expect(screen.getByText(/dark mode/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run all renderer tests**

Run: `npm test`
Expected: all tests pass (App, Button, Input, SearchBar, Card, Sidebar, AppShell)

- [ ] **Step 4: Commit**

```bash
git add src/renderer/App.tsx tests/renderer/App.test.tsx
git commit -m "feat: wire App.tsx to ThemeProvider, Router, and AppShell"
```

---

## Task 11: Smoke test — verify the running application

**Files:**
- No new files — verification only

- [ ] **Step 1: Run the full test suite**

```bash
npm test && pytest tests/python/ -v
```

Expected: all renderer + Python tests pass.

- [ ] **Step 2: Start the dev server**

```bash
npm run dev
```

Expected:
- Vite dev server starts on `http://localhost:5173`
- Python backend starts on `127.0.0.1:7777`
- Electron window opens

Verify in the window:
1. **Sidebar** visible on the left with "Clinical Registry" title
2. **Navigation items** visible: Observations, Clinical Protocols, Research Notes, Medication Ledger
3. **Search bar** at the top of the main content area
4. **Dashboard placeholder** text visible in the main area
5. **Dark mode toggle** visible at the bottom of the sidebar
6. **"New Documentation" button** visible at the bottom of the sidebar
7. Click "Clinical Protocols" — URL changes to `/quiz`, quiz placeholder appears
8. Click the dark mode toggle — theme switches to dark (dark background, light text)
9. Click "Observations" — returns to dashboard

- [ ] **Step 3: Check for visual design system compliance**

Visually confirm:
- No 1px solid borders (only ghost borders at <15% opacity)
- Warm parchment background (`#fbf9f3`)
- Dot-grid texture visible at very low opacity
- Newsreader serif font for headings
- Space Grotesk sans-serif for body text
- Teal primary colour (`#2D5A54`) for active nav and buttons
- Dark mode: inverted palette, readable contrast

- [ ] **Step 4: Update TODO.md**

Mark these Phase 5 items as complete (`[x]`):
- `[ ] Confirm GUI framework choice (Electron vs Tauri)` → `[x]` (Electron, already confirmed)
- `[ ] Set up project with React + Tailwind CSS` → `[x]` (done in Phase 0)
- `[ ] Implement "The Archival Protocol" design system` → `[x]`
  - `[ ] Colour tokens (surface hierarchy, accent colours)` → `[x]`
  - `[ ] Typography scale (Newsreader, Space Grotesk, IBM Plex Mono)` → `[x]`
  - `[ ] Component library (buttons, inputs, cards per DESIGN.md)` → `[x]`
  - `[ ] The "No-Line" Rule enforcement` → `[x]`
- `[ ] Persistent left sidebar navigation` → `[x]`
- `[ ] Universal search bar` → `[x]`
- `[ ] Dark mode support (high-contrast clinical theme)` → `[x]`

Update `Last Updated` date to `2026-04-02`.

- [ ] **Step 5: Final commit**

```bash
git add TODO.md
git commit -m "chore: mark Phase 5 complete in TODO"
```

---

## Summary

| Task | What | Type |
|------|------|------|
| 1 | Install react-router-dom + PostCSS config | Setup |
| 2 | Full Archival Protocol design tokens (Tailwind + CSS custom properties) | Design system |
| 3 | ThemeProvider context with dark mode toggle | Design system |
| 4 | Button component (3 variants) — TDD | Component + tests |
| 5 | Input + SearchBar components — TDD | Component + tests |
| 6 | Card + Tag components — TDD | Component + tests |
| 7 | MasteryIndicator component | Component |
| 8 | Sidebar navigation with active states — TDD | Component + tests |
| 9 | AppShell layout + page stubs + Router — TDD | Architecture + tests |
| 10 | Wire App.tsx to ThemeProvider + Router + AppShell | Integration |
| 11 | Smoke test + visual verification + update TODO | Verification |
