#!/usr/bin/env bash
set -euo pipefail

# Build a complete ChromaDB with all document types and upload to a GitHub Release
# so the personal-build workflow can download it during CI.
#
# Usage: bash scripts/upload-personal-data.sh
#
# Prerequisites:
#   - gh CLI authenticated (gh auth login)
#   - Archive at ../studyBotcode-archive/data/ with:
#     - chroma_db/          (target ChromaDB)
#     - cmgs/structured/    (CMG JSON files)
#     - personal_docs/structured/ (REFdocs + CPDdocs markdown)
#     - notes_md/cleaned/   (cleaned notability notes)

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

PYTHONPATH="$REPO_ROOT/src/python"

echo "=== Building complete ChromaDB with all document types ==="

# --- Stage 1: CMG Guidelines ---
CMG_STRUCT="$ARCHIVE_DIR/cmgs/structured"
if [[ -d "$CMG_STRUCT" ]] && ls "$CMG_STRUCT"/*.json &>/dev/null; then
  echo "--- Ingesting CMG guidelines ---"
  PYTHONPATH="$PYTHONPATH" python3 -c "
from pipeline.cmg.chunker import chunk_and_ingest
chunk_and_ingest(structured_dir='$CMG_STRUCT', db_path='$ARCHIVE_DIR/chroma_db')
import chromadb
client = chromadb.PersistentClient(path='$ARCHIVE_DIR/chroma_db')
col = client.get_or_create_collection('cmg_guidelines')
print(f'  cmg_guidelines: {col.count()} chunks')
"
else
  echo "--- Skipping CMGs (no structured data at $CMG_STRUCT) ---"
fi

# --- Stage 2: Personal Docs (REFdocs + CPDdocs) ---
PD_STRUCT="$ARCHIVE_DIR/personal_docs/structured"
if [[ -d "$PD_STRUCT" ]]; then
  echo "--- Ingesting personal docs (REFdocs + CPDdocs) ---"
  PYTHONPATH="$PYTHONPATH" python3 -c "
from pathlib import Path
from pipeline.personal_docs.chunker import chunk_and_ingest_directory
result = chunk_and_ingest_directory(Path('$PD_STRUCT'), Path('$ARCHIVE_DIR/chroma_db'))
print(f'  Processed: {result[\"processed\"]} files, {result[\"total_chunks\"]} chunks ({result[\"errors\"]} errors)')
import chromadb
client = chromadb.PersistentClient(path='$ARCHIVE_DIR/chroma_db')
col = client.get_or_create_collection('paramedic_notes')
ref = col.get(where={'source_type': 'ref_doc'})
cpd = col.get(where={'source_type': 'cpd_doc'})
print(f'  paramedic_notes: ref_doc={len(ref[\"ids\"])}, cpd_doc={len(cpd[\"ids\"])}')
"
else
  echo "--- Skipping personal docs (no structured data at $PD_STRUCT) ---"
fi

# --- Stage 3: Notability Notes ---
NOTES_CLEANED="$ARCHIVE_DIR/notes_md/cleaned"
if [[ -d "$NOTES_CLEANED" ]]; then
  echo "--- Ingesting notability notes ---"
  PYTHONPATH="$PYTHONPATH" python3 -c "
from pathlib import Path
from pipeline.chunker import chunk_and_ingest

cleaned_dir = Path('$NOTES_CLEANED')
md_files = sorted(cleaned_dir.rglob('*.md'))
total = 0
for md_path in md_files:
    result = chunk_and_ingest(md_path, Path('$ARCHIVE_DIR/chroma_db'))
    total += result.get('chunk_count', 0)
print(f'  Ingested {len(md_files)} notability files, {total} chunks')
import chromadb
client = chromadb.PersistentClient(path='$ARCHIVE_DIR/chroma_db')
col = client.get_or_create_collection('paramedic_notes')
notes = col.get(where={'source_type': 'notability_note'})
print(f'  paramedic_notes: notability_note={len(notes[\"ids\"])}')
"
else
  echo "--- Skipping notability notes (no cleaned data at $NOTES_CLEANED) ---"
fi

# --- Summary ---
echo "--- ChromaDB summary ---"
PYTHONPATH="$PYTHONPATH" python3 -c "
import chromadb
client = chromadb.PersistentClient(path='$ARCHIVE_DIR/chroma_db')
for name in ['cmg_guidelines', 'paramedic_notes']:
    try:
        col = client.get_collection(name)
        print(f'  {name}: {col.count()} chunks')
    except Exception:
        print(f'  {name}: not found')
"

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
