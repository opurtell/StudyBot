# Logo Design Brief — Clinical Recall Assistant

## App Overview

**Clinical Recall Assistant** is a desktop study app for ACT Ambulance Service paramedics. It quizzes users on clinical guidelines, medication doses, and clinical skills using active-recall flashcards, with AI-powered feedback grounded in authoritative source material. Think of it as a focused, high-quality study companion — not a gamified flashcard toy, and not a clinical decision tool.

## Brand Personality

- **Authority without arrogance** — an expert study partner, clinical and precise
- **Calm confidence** — supportive, not casual; straightforward, not chatty
- **Archival and editorial** — the app uses a warm, library-like design system ("The Archival Protocol") inspired by clinical archives and medical reference libraries

## Core Brand Colours

| Role | Hex | Notes |
|------|-----|-------|
| Primary (dark teal/ink) | `#2D5A54` | High-authority actions, brand anchor |
| Highlight accent | `#DAE058` | Yellow-green, active states and critical highlights |
| Surface base (parchment) | `#FBF9F3` | Warm off-white backgrounds |
| Dark mode surface | `#1A1C1E` | Dark background |

The logo should work on both light (`#FBF9F3`) and dark (`#1A1C1E`) backgrounds.

## Design Direction

The logo should feel **clinical, archival, and modern**. Think medical textbook meets editorial design — not cartoonish, not overly complex. It should work at small sizes (taskbar/dock icon) and large (splash screen, about panel).

Possible conceptual hooks (not prescriptive):
- An open book or folded document with a clinical cross or caduceus element
- A stylised archive card or index card
- A minimalist medical motif (heart line, cross, shield) combined with a study/recall element
- Typography-led mark using "CRA" or "Clinical Recall"

The logo must be legible at 16x16px (favicon/taskbar size).

## Required Deliverables

Provide all of the following in a single ZIP. Name files as shown — they map directly into the build pipeline.

### 1. Source File
| File | Format | Notes |
|------|--------|-------|
| `logo-source.svg` | SVG (vector) | Master editable file. All text outlined. Layers named. |

### 2. macOS App Icon
| File | Size | Notes |
|------|------|-------|
| `icon.icns` | Multi-size ICNS | Must contain: 16, 32, 64, 128, 256, 512, 1024px |
| `icon_1024.png` | 1024x1024px | Used to generate the `.icns` via `iconutil` |

macOS icon should follow the standard rounded-rectangle (squircle) app icon shape. Design the full-bleed artwork inside the squircle — **do not** add the rounded corners yourself; macOS applies them. Leave ~10% padding from edges for the mask.

### 3. Windows App Icon
| File | Size | Notes |
|------|------|-------|
| `icon.ico` | Multi-size ICO | Must contain: 16, 32, 48, 64, 128, 256px |

Windows icons are flat (no squircle mask). Provide a clean, square version.

### 4. Web / Renderer Assets
| File | Size | Notes |
|------|------|-------|
| `favicon-16.png` | 16x16px | Browser tab icon |
| `favicon-32.png` | 32x32px | Browser tab icon (retina) |
| `favicon.svg` | SVG | Modern browser favicon |
| `apple-touch-icon.png` | 180x180px | iOS home screen (if ever relevant) |

### 5. Splash / About Panel
| File | Size | Notes |
|------|------|-------|
| `logo-light.png` | 512x512px | Full logo on transparent or parchment `#FBF9F3` background |
| `logo-dark.png` | 512x512px | Full logo on transparent or dark `#1A1C1E` background |

## File Placement in Repo

Icons will be placed at:
- `build/icon.icns` — macOS (electron-builder reads this automatically)
- `build/icon.ico` — Windows (electron-builder reads this automatically)
- `public/favicon-16.png`, `public/favicon-32.png`, `public/favicon.svg` — Vite serves these as-is
- `src/renderer/assets/logo-light.png`, `src/renderer/assets/logo-dark.png` — used in-app

## Typography Reference

If the logo includes text:
- **Display serif:** Newsreader — used for headlines in the app
- **Body sans-serif:** Space Grotesk — used for labels and UI text
- **Monospace:** IBM Plex Mono — used for data display

## Constraints

- No gradients that rely on transparency (they break at small sizes)
- Must be legible at 16x16px
- No text smaller than 8pt equivalent at smallest icon size
- Flat or minimal shading — the app's design system avoids heavy shadows
- Australian English spelling if any text is included
- No medical symbols that could be confused with an actual clinical device or alert
- Avoid the Rod of Asclepius/caduceus if it looks like a generic medical clip-art logo — prefer something more distinctive

## Questions?

Reach out via the project channel. Happy to provide screenshots of the current UI for visual context.
