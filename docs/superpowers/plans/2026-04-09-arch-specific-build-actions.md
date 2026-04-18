# Architecture-Specific Build Actions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the two GitHub Actions build workflows so each can run a single architecture on demand via a dropdown selector.

**Architecture:** A `prepare` job computes a filtered matrix JSON from the `arch` input. The `build` job consumes that matrix. A `draft-release` job always runs afterward. Tag-triggered release builds ignore the `arch` input and always build all 3.

**Tech Stack:** GitHub Actions (workflow_dispatch, matrix strategy, JSON outputs)

---

### Task 1: Rewrite `release-build.yml`

**Files:**
- Modify: `.github/workflows/release-build.yml`

- [ ] **Step 1: Write the complete replacement workflow**

Replace the entire file with:

```yaml
name: Release Build

on:
  push:
    tags:
      - "v*"
  workflow_dispatch:
    inputs:
      arch:
        description: "Target architecture"
        type: choice
        options:
          - all
          - mac-arm64
          - mac-x64
          - win-x64
        default: all
      version:
        description: "Version tag (e.g. v0.1.0)"
        required: false

env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true

jobs:
  prepare:
    runs-on: ubuntu-latest
    outputs:
      matrix: ${{ steps.set.outputs.matrix }}
    steps:
      - name: Compute build matrix
        id: set
        run: |
          # Tag-triggered builds always build all
          if [[ "${{ github.event_name }}" == "push" ]]; then
            SELECTED="all"
          else
            SELECTED="${{ inputs.arch }}"
          fi

          ALL='[
            {"arch":"mac-arm64","os":"macos-latest","backend_cmd":"bash scripts/package-backend.sh arm64","verify_cmd":"bash scripts/verify-backend-payload.sh","eb_args":"--arm64"},
            {"arch":"mac-x64","os":"macos-latest","backend_cmd":"bash scripts/package-backend.sh x64","verify_cmd":"bash scripts/verify-backend-payload.sh","eb_args":"--x64"},
            {"arch":"win-x64","os":"windows-latest","backend_cmd":"pwsh -File scripts/package-backend.ps1","verify_cmd":"pwsh -File scripts/verify-backend-payload.ps1","eb_args":"--win --x64"}
          ]'

          if [[ "$SELECTED" == "all" ]]; then
            MATRIX="$ALL"
          else
            MATRIX=$(echo "$ALL" | jq -c --arg sel "$SELECTED" 'map(select(.arch == $sel))')
          fi

          echo "matrix=$MATRIX" >> "$GITHUB_OUTPUT"
          echo "Selected: $SELECTED"
          echo "$MATRIX" | jq .

  build:
    needs: prepare
    strategy:
      matrix:
        include: ${{ fromJson(needs.prepare.outputs.matrix) }}
      fail-fast: false
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "22"
      - run: npm ci
      - run: ${{ matrix.backend_cmd }}
      - run: ${{ matrix.verify_cmd }}
      - run: npx vite build && npx electron-builder ${{ matrix.eb_args }}
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      - uses: actions/upload-artifact@v4
        with:
          name: ${{ matrix.arch }}
          path: release/**
          retention-days: 1

  draft-release:
    needs: build
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/download-artifact@v4
        with:
          path: release-artifacts
      - name: Flatten artifacts
        run: |
          mkdir -p release-staging
          find release-artifacts -type f \( -name '*.dmg' -o -name 'StudyBot*.exe' \) ! -path '*/win-unpacked/*' -exec cp {} release-staging/ \;
          echo "Staged files:"
          ls -lh release-staging/
      - name: Determine version
        id: version
        run: |
          VERSION="${{ inputs.version }}"
          if [[ -z "$VERSION" ]]; then
            if [[ "$GITHUB_REF" == refs/tags/* ]]; then
              VERSION="${GITHUB_REF#refs/tags/}"
            else
              VERSION="v$(date +%Y.%m.%d-%H%M)"
            fi
          fi
          echo "tag=$VERSION" >> "$GITHUB_OUTPUT"
      - name: Create draft release
        uses: softprops/action-gh-release@v2
        with:
          tag_name: ${{ steps.version.outputs.tag }}
          draft: true
          name: "Standard Build ${{ steps.version.outputs.tag }}"
          files: release-staging/*
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

- [ ] **Step 2: Validate YAML syntax**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/release-build.yml')); print('YAML valid')"`
Expected: `YAML valid`

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/release-build.yml
git commit -m "refactor: add arch selector to release build workflow"
```

---

### Task 2: Rewrite `personal-build.yml`

**Files:**
- Modify: `.github/workflows/personal-build.yml`

- [ ] **Step 1: Write the complete replacement workflow**

Replace the entire file with:

```yaml
name: Personal Build

on:
  workflow_dispatch:
    inputs:
      arch:
        description: "Target architecture"
        type: choice
        options:
          - all
          - mac-arm64
          - mac-x64
          - win-x64
        default: all
      version:
        description: "Version tag (e.g. v0.2.0)"
        required: false

env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true

jobs:
  prepare:
    runs-on: ubuntu-latest
    outputs:
      matrix: ${{ steps.set.outputs.matrix }}
    steps:
      - name: Compute build matrix
        id: set
        run: |
          SELECTED="${{ inputs.arch }}"

          ALL='[
            {"arch":"mac-arm64","os":"macos-latest","backend_cmd":"bash scripts/package-backend.sh arm64","verify_cmd":"bash scripts/verify-backend-payload.sh","eb_args":"--config electron-builder.personal.yml --arm64 --publish never"},
            {"arch":"mac-x64","os":"macos-latest","backend_cmd":"bash scripts/package-backend.sh x64","verify_cmd":"bash scripts/verify-backend-payload.sh","eb_args":"--config electron-builder.personal.yml --x64 --publish never"},
            {"arch":"win-x64","os":"windows-latest","backend_cmd":"pwsh -File scripts/package-backend.ps1","verify_cmd":"pwsh -File scripts/verify-backend-payload.ps1","eb_args":"--config electron-builder.personal.yml --win --x64 --publish never"}
          ]'

          if [[ "$SELECTED" == "all" ]]; then
            MATRIX="$ALL"
          else
            MATRIX=$(echo "$ALL" | jq -c --arg sel "$SELECTED" 'map(select(.arch == $sel))')
          fi

          echo "matrix=$MATRIX" >> "$GITHUB_OUTPUT"
          echo "Selected: $SELECTED"
          echo "$MATRIX" | jq .

  build:
    needs: prepare
    strategy:
      matrix:
        include: ${{ fromJson(needs.prepare.outputs.matrix) }}
      fail-fast: false
    runs-on: ${{ matrix.os }}
    env:
      PERSONAL_BUILD: "1"
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "22"
      - name: Download personal ChromaDB
        uses: dsaltares/fetch-gh-release-asset@1.1.2
        with:
          version: "tags/personal-data"
          file: "chroma_db.tar.gz"
      - name: Extract personal ChromaDB (macOS/Linux)
        if: runner.os != 'Windows'
        run: |
          mkdir -p build/resources/data
          tar -xzf chroma_db.tar.gz -C build/resources/data
          echo "ChromaDB contents:"
          ls -lh build/resources/data/chroma_db/
      - name: Extract personal ChromaDB (Windows)
        if: runner.os == 'Windows'
        run: |
          New-Item -ItemType Directory -Force -Path build\resources\data | Out-Null
          tar -xzf chroma_db.tar.gz -C build\resources\data
          Write-Host "ChromaDB contents:"
          Get-ChildItem -Recurse build\resources\data\chroma_db | Format-Table Name, Length
      - run: npm ci
      - run: ${{ matrix.backend_cmd }}
      - run: ${{ matrix.verify_cmd }}
      - run: npx vite build && npx electron-builder ${{ matrix.eb_args }}
      - uses: actions/upload-artifact@v4
        with:
          name: ${{ matrix.arch }}-personal
          path: release/**
          retention-days: 1

  draft-release:
    needs: build
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/download-artifact@v4
        with:
          path: release-artifacts
      - name: Flatten artifacts
        run: |
          mkdir -p release-staging
          find release-artifacts -type f \( -name '*.dmg' -o -name 'StudyBot*.exe' \) ! -path '*/win-unpacked/*' -exec cp {} release-staging/ \;
          echo "Staged files:"
          ls -lh release-staging/
      - name: Determine version
        id: version
        run: |
          VERSION="${{ inputs.version }}"
          if [[ -z "$VERSION" ]]; then
            VERSION="v$(date +%Y.%m.%d-%H%M)"
          fi
          echo "tag=personal-${VERSION}" >> "$GITHUB_OUTPUT"
      - name: Push tag
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git tag -f ${{ steps.version.outputs.tag }}
          git push origin ${{ steps.version.outputs.tag }} --force
      - name: Create draft release
        uses: softprops/action-gh-release@v2
        with:
          tag_name: ${{ steps.version.outputs.tag }}
          draft: true
          name: "Personal Build ${{ steps.version.outputs.tag }}"
          body: |
            Personal build including all data sources:
            - ACTAS CMGs (clinical guidelines)
            - Notability notes (380 cleaned markdown files)
            - REFdocs & CPDdocs (personal study documents)
          files: release-staging/*
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

- [ ] **Step 2: Validate YAML syntax**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/personal-build.yml')); print('YAML valid')"`
Expected: `YAML valid`

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/personal-build.yml
git commit -m "refactor: add arch selector to personal build workflow"
```

---

### Task 3: Verify no regressions

**Files:** None (verification only)

- [ ] **Step 1: Confirm both YAML files parse cleanly**

Run: `python3 -c "import yaml; [yaml.safe_load(open(f'.github/workflows/{f}')) for f in ['release-build.yml','personal-build.yml']]; print('Both valid')"`
Expected: `Both valid`

- [ ] **Step 2: Grep for any references to old job names**

Run: `grep -rn 'build-mac-arm64\|build-mac-x64\|build-win-x64' .github/ scripts/ package.json || echo "No stale references found"`
Expected: `No stale references found`

- [ ] **Step 3: Final commit (if any fixes needed)**

Only if step 2 found stale references that need cleanup.
