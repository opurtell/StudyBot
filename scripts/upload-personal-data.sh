#!/usr/bin/env bash
set -euo pipefail

# Upload the pre-built ChromaDB from the archive to a GitHub Release
# so the personal-build workflow can download it during CI.
#
# Usage: bash scripts/upload-personal-data.sh
#
# Prerequisites:
#   - gh CLI authenticated (gh auth login)
#   - Archive at ../studyBotcode-archive/data/chroma_db/

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ARCHIVE_DIR="$REPO_ROOT/../studyBotcode-archive/data"
RELEASE_TAG="personal-data"
ASSET_NAME="chroma_db.tar.gz"

if ! command -v gh &>/dev/null; then
  echo "ERROR: gh CLI not found. Install from https://cli.github.com"
  exit 1
fi

if [[ ! -d "$ARCHIVE_DIR/chroma_db" ]]; then
  echo "ERROR: Archive chroma_db not found at $ARCHIVE_DIR/chroma_db"
  exit 1
fi

DB_SIZE=$(du -sh "$ARCHIVE_DIR/chroma_db" | cut -f1)
echo "=== Uploading personal ChromaDB ($DB_SIZE) ==="

TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

echo "--- Creating tarball ---"
tar -czf "$TMPDIR/$ASSET_NAME" -C "$ARCHIVE_DIR" chroma_db

TARBALL_SIZE=$(du -sh "$TMPDIR/$ASSET_NAME" | cut -f1)
echo "    Tarball size: $TARBALL_SIZE"

echo "--- Ensuring release exists ---"
if ! gh release view "$RELEASE_TAG" &>/dev/null; then
  gh release create "$RELEASE_TAG" \
    --title "Personal Data" \
    --notes "Pre-built ChromaDB index containing all source types (CMGs, notability notes, personal docs).

This release is used by the personal-build workflow. Update by running:
  bash scripts/upload-personal-data.sh"
  echo "    Created release: $RELEASE_TAG"
else
  echo "    Release already exists: $RELEASE_TAG"
fi

echo "--- Uploading tarball ---"
gh release upload "$RELEASE_TAG" "$TMPDIR/$ASSET_NAME" --clobber

echo "=== Done ==="
echo "    Release: $(gh release view "$RELEASE_TAG" --json url -q .url)"
echo ""
echo "To trigger a personal build:"
echo "  gh workflow run personal-build.yml"
