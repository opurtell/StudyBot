#!/usr/bin/env bash
set -euo pipefail

PYTHON_STANDALONE_TAG="20260325"
PYTHON_VERSION="3.12.13"

usage() {
  echo "Usage: $0 <arch>"
  echo "  arch: arm64 | x64"
  exit 1
}

ARCH="${1:-}"
if [[ "$ARCH" != "arm64" && "$ARCH" != "x64" ]]; then
  usage
fi

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT_DIR="$REPO_ROOT/build/resources/backend"

if [[ "$ARCH" == "arm64" ]]; then
  PBS_ARCH="aarch64"
else
  PBS_ARCH="x86_64"
fi

PBS_TARBALL="cpython-${PYTHON_VERSION}+${PYTHON_STANDALONE_TAG}-${PBS_ARCH}-apple-darwin-install_only.tar.gz"
PBS_URL="https://github.com/indygreg/python-build-standalone/releases/download/${PYTHON_STANDALONE_TAG}/${PBS_TARBALL}"

echo "=== Packaging backend for macOS $ARCH ==="
echo "    Python: ${PYTHON_VERSION}"
echo "    Output: ${OUTPUT_DIR}"

rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"

DOWNLOAD_DIR="$REPO_ROOT/build/.cache/python-standalone"
mkdir -p "$DOWNLOAD_DIR"
TARBALL_PATH="$DOWNLOAD_DIR/$PBS_TARBALL"

if [[ ! -f "$TARBALL_PATH" ]]; then
  echo "--- Downloading standalone Python ---"
  echo "    URL: $PBS_URL"
  curl -fSL -o "$TARBALL_PATH" "$PBS_URL"
else
  echo "--- Using cached standalone Python ---"
fi

EXTRACT_DIR="$REPO_ROOT/build/.staging/backend-mac-$ARCH"
rm -rf "$EXTRACT_DIR"
mkdir -p "$EXTRACT_DIR"

echo "--- Extracting standalone Python ---"
tar -xzf "$TARBALL_PATH" -C "$EXTRACT_DIR"

PYTHON_PREFIX=$(ls -d "$EXTRACT_DIR"/python/)
if [[ -z "$PYTHON_PREFIX" ]]; then
  echo "ERROR: Could not find extracted python/ directory"
  exit 1
fi
echo "    Extracted to: $PYTHON_PREFIX"

echo "--- Staging Python runtime ---"
mkdir -p "$OUTPUT_DIR/bin"
mkdir -p "$OUTPUT_DIR/lib"

cp "$PYTHON_PREFIX/bin/python3" "$OUTPUT_DIR/bin/python3"
cp "$PYTHON_PREFIX/bin/python3.12" "$OUTPUT_DIR/bin/python3.12" 2>/dev/null || true

if [[ -d "$PYTHON_PREFIX/lib/python3.12" ]]; then
  cp -R "$PYTHON_PREFIX/lib/python3.12" "$OUTPUT_DIR/lib/python3.12"
fi

for dylib in "$PYTHON_PREFIX"/lib/libpython*.dylib; do
  if [[ -f "$dylib" ]]; then
    cp "$dylib" "$OUTPUT_DIR/lib/"
  fi
done

echo "--- Copying backend source ---"
mkdir -p "$OUTPUT_DIR/app/src"
rsync -a --exclude='__pycache__' "$REPO_ROOT/src/python/" "$OUTPUT_DIR/app/src/python/"

echo "--- Installing dependencies from pyproject.toml ---"
STAGED_PYTHON="$OUTPUT_DIR/bin/python3"
if [[ ! -x "$STAGED_PYTHON" ]]; then
  echo "ERROR: Staged python3 not found at $STAGED_PYTHON"
  exit 1
fi
chmod +x "$STAGED_PYTHON"

$STAGED_PYTHON -m pip install --no-cache-dir --no-compile --target "$OUTPUT_DIR/lib" "$REPO_ROOT"

echo "--- Verifying stdlib imports ---"
PYTHONPATH="$OUTPUT_DIR/lib:$OUTPUT_DIR/app/src/python" "$STAGED_PYTHON" -c "
import os, sys, json
print(f'Python: {sys.version}')
print(f'prefix: {sys.prefix}')
print(f'os from: {os.__file__}')
assert 'lib' in os.__file__, f'stdlib not in staged lib: {os.__file__}'
print('stdlib: OK')
"

echo "--- Verifying third-party imports ---"
PYTHONPATH="$OUTPUT_DIR/lib:$OUTPUT_DIR/app/src/python" "$STAGED_PYTHON" -c "
import fastapi, uvicorn, chromadb
print(f'fastapi {fastapi.__version__}')
print(f'uvicorn {uvicorn.__version__}')
print(f'chromadb {chromadb.__version__}')
print('third-party deps: OK')
"

echo "--- Verifying backend code imports ---"
PYTHONPATH="$OUTPUT_DIR/lib:$OUTPUT_DIR/app/src/python" "$STAGED_PYTHON" -c "
import main
print('backend code: OK')
"

echo "--- Cleaning temp artifacts ---"
rm -rf "$EXTRACT_DIR"

echo "--- Pre-building ChromaDB index from bundled CMGs ---"
CHROMA_OUTPUT="$REPO_ROOT/build/resources/data/chroma_db"
rm -rf "$CHROMA_OUTPUT"
mkdir -p "$CHROMA_OUTPUT"
PYTHONPATH="$OUTPUT_DIR/lib:$OUTPUT_DIR/app/src/python" "$STAGED_PYTHON" -c "
from pipeline.cmg.chunker import chunk_and_ingest
chunk_and_ingest(structured_dir='$REPO_ROOT/data/cmgs/structured', db_path='$CHROMA_OUTPUT')
import chromadb
client = chromadb.PersistentClient(path='$CHROMA_OUTPUT')
col = client.get_or_create_collection('cmg_guidelines')
print(f'Pre-built index: {col.count()} chunks')
"

PAYLOAD_SIZE=$(du -sh "$OUTPUT_DIR" | cut -f1)
echo "=== Backend payload ready at $OUTPUT_DIR ($PAYLOAD_SIZE) ==="
