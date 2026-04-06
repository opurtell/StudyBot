#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PAYLOAD_DIR="$REPO_ROOT/build/resources/backend"

echo "=== Verifying backend payload ==="

ERRORS=0

if [[ ! -d "$PAYLOAD_DIR" ]]; then
  echo "FAIL: Payload directory missing: $PAYLOAD_DIR"
  exit 1
fi

PYTHON_BIN="$PAYLOAD_DIR/bin/python3"
if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "FAIL: python3 not found or not executable: $PYTHON_BIN"
  ERRORS=$((ERRORS + 1))
else
  echo "OK:   python3 binary found"
fi

if [[ ! -d "$PAYLOAD_DIR/lib" ]]; then
  echo "FAIL: lib/ directory missing"
  ERRORS=$((ERRORS + 1))
else
  echo "OK:   lib/ directory exists"
fi

if [[ ! -d "$PAYLOAD_DIR/app/src/python" ]]; then
  echo "FAIL: Backend source missing: app/src/python/"
  ERRORS=$((ERRORS + 1))
else
  echo "OK:   Backend source present"
fi

if [[ $ERRORS -gt 0 ]]; then
  echo "=== Skipping import checks ($ERRORS structural errors) ==="
  exit 1
fi

echo "--- Checking stdlib imports ---"
PYTHONPATH="$PAYLOAD_DIR/lib:$PAYLOAD_DIR/app/src/python" "$PYTHON_BIN" -c "
import os, sys, json
assert 'lib' in os.__file__, f'stdlib not from staged lib: {os.__file__}'
print('OK:   stdlib imports work')
" || { echo "FAIL: stdlib imports failed"; exit 1; }

echo "--- Checking third-party imports ---"
PYTHONPATH="$PAYLOAD_DIR/lib:$PAYLOAD_DIR/app/src/python" "$PYTHON_BIN" -c "
import fastapi, uvicorn, chromadb
print('OK:   third-party imports work')
" || { echo "FAIL: third-party imports failed"; exit 1; }

echo "--- Checking backend code imports ---"
PYTHONPATH="$PAYLOAD_DIR/lib:$PAYLOAD_DIR/app/src/python" "$PYTHON_BIN" -c "
import main
print('OK:   backend code imports work')
" || { echo "FAIL: backend code imports failed"; exit 1; }

echo "=== All checks passed ==="
