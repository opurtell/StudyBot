# Fix Per-Architecture macOS Builds

**Created:** 2026-04-06
**Status:** Complete
**Blocks:** Clean-machine validation (Phase F3/F4), arm64 distribution

## Problem

Running `npm run build:mac-x64` produces both an x64 and an arm64 DMG. The arm64 DMG contains the x64 backend payload (x86_64 Python binary, x86_64 native wheels, x86_64 `libpython3.12.dylib`). On an Apple Silicon Mac without Rosetta 2, the app would fail to start the backend.

## Root Cause

Two independent issues combine:

### 1. electron-builder.yml lists both architectures

```yaml
mac:
  target:
    - target: dmg
      arch:
        - arm64
        - x64
```

The `--x64` or `--arm64` CLI flag does **not** override this list. electron-builder builds every arch listed in the yml regardless of the flag.

### 2. Single flat backend payload directory

`build/resources/backend/` is overwritten each time the packaging script runs. The directory contains architecture-specific binaries:

- `bin/python3` — x86_64 or aarch64 ELF/Mach-O binary
- `lib/libpython3.12.dylib` — matched to the Python binary
- `lib/` installed packages — contain architecture-specific `.so`/`.dylib` files for `chromadb`, `onnxruntime`, `numpy`, `uvloop`, `watchfiles`, etc.

When `package-backend.sh x64` runs, the payload is x86_64. When electron-builder then packages both archs, both DMGs bundle this same x64 payload.

## Fix

### Step 1: Remove the arch list from electron-builder.yml

Change the mac target to omit the `arch` key entirely so the CLI flag controls which arch gets built.

**Before:**

```yaml
mac:
  target:
    - target: dmg
      arch:
        - arm64
        - x64
```

**After:**

```yaml
mac:
  target:
    - target: dmg
```

With this change:

- `electron-builder --arm64` builds an arm64 DMG only
- `electron-builder --x64` builds an x64 DMG only
- `electron-builder` (no flag) builds the host architecture

### Step 2: No changes to packaging scripts

The existing scripts already accept an arch argument and output to the same flat directory:

- `bash scripts/package-backend.sh arm64` — stages arm64 payload
- `bash scripts/package-backend.sh x64` — stages x64 payload

The npm scripts already chain them correctly:

```
build:mac-arm64 → build:backend-mac-arm64 → vite build → electron-builder --arm64
build:mac-x64   → build:backend-mac-x64   → vite build → electron-builder --x64
```

### Step 3: Build sequentially, never in parallel

Each full build overwrites `build/resources/backend/`. Builds must run one at a time:

```bash
npm run build:mac-arm64
# DMG appears at release/Clinical Recall Assistant-0.1.0-arm64.dmg
# Copy or rename it before the next build

npm run build:mac-x64
# DMG appears at release/Clinical Recall Assistant-0.1.0.dmg
```

If both DMGs are needed in the same `release/` directory, rename the first before running the second.

### Step 4: Update the Windows target similarly (consistency)

The Windows target in `electron-builder.yml` already uses a single arch so no change is needed:

```yaml
win:
  target:
    - target: nsis
      arch:
        - x64
```

Optionally simplify to:

```yaml
win:
  target:
    - target: nsis
```

The CLI `--win --x64` already controls this. No functional impact either way.

## Files Changed

| File | Change |
|------|--------|
| `electron-builder.yml` | Remove `arch` list from mac target |

## Verification

After applying the fix:

1. `rm -rf build/resources/backend release/`
2. `npm run build:mac-arm64`
   - Confirm exactly one DMG in `release/`
   - Confirm DMG filename contains `arm64`
   - Confirm `build/resources/backend/bin/python3` is `aarch64` Mach-O
3. Save the arm64 DMG elsewhere
4. `npm run build:mac-x64`
   - Confirm exactly one DMG in `release/`
   - Confirm DMG filename does not contain `arm64`
   - Confirm `build/resources/backend/bin/python3` is `x86_64` Mach-O
5. Update `Guides/standalone-packaging-macos-windows.md` build notes

## CI Workflow

The GitHub Actions workflow (`.github/workflows/release-build.yml`) already handles this correctly. Each matrix job runs on the matching runner (`macos-latest` for arm64, `macos-13` for x64) and stages its own payload before building. No CI changes needed.
