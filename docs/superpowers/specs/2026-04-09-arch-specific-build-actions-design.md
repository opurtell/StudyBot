# Architecture-Specific Build Actions

**Date:** 2026-04-09

## Problem

The current `release-build.yml` and `personal-build.yml` workflows always build all 3 architectures (mac-arm64, mac-x64, win-x64) in parallel. There is no way to trigger a single architecture build — useful for testing, iteration, or when only one platform is needed.

## Design

Replace both workflow files with versions that accept an `arch` input, allowing selection of a single architecture or all three.

### Workflows

**`release-build.yml`** — triggers on tag push `v*` OR manual dispatch.
- Inputs: `arch` (choice: `mac-arm64` | `mac-x64` | `win-x64` | `all`, default `all`), `version` (optional string)
- Tag push always builds all 3 (ignores `arch` input).

**`personal-build.yml`** — triggers on manual dispatch only.
- Inputs: `arch` (choice: `mac-arm64` | `mac-x64` | `win-x64` | `all`, default `all`), `version` (optional string)

### Job structure (both workflows)

1. **`prepare`** job — evaluates inputs, outputs a filtered JSON matrix.
2. **`build`** job — runs the filtered matrix. Each entry: backend package → verify → vite build → electron-builder → upload artifact.
3. **`draft-release`** job — always runs after build completes. Downloads artifacts, creates draft release with version tag.

### Matrix filtering

The `prepare` job builds a JSON array of matrix entries:
- `all` → all 3 entries
- Specific arch → single entry
- Tag push (release only) → always all 3

Each matrix entry carries: `arch`, `os`, `runner_suffix` (for artifact naming), `backend_cmd`, `verify_cmd`, `eb_args`, and personal-specific fields (`personal_build_env`, `chromadb_download`).

### Draft release

Always created, regardless of how many architectures were built. For single-arch runs, the release contains only that artifact. Version determination logic unchanged from current workflows.

### What stays the same

- Backend packaging scripts (`package-backend.sh`, `package-backend.ps1`)
- Verification scripts (`verify-backend-payload.sh`, `verify-backend-payload.ps1`)
- ChromaDB handling (pre-build for release, download for personal)
- Personal build tag push step
- `electron-builder.personal.yml` usage for personal builds
- Artifact naming conventions

### What changes

- 3 separate named jobs (`build-mac-arm64`, `build-mac-x64`, `build-win-x64`) become a single parametric `build` job with a matrix
- A `prepare` job is added to compute the filtered matrix
- `draft-release` depends on `build` instead of listing 3 specific jobs
- Manual dispatch gets the `arch` selector input

## Scope

- Only modifies `.github/workflows/release-build.yml` and `.github/workflows/personal-build.yml`
- No changes to npm scripts, packaging scripts, or electron-builder config
