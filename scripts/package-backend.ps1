<#
.SYNOPSIS
    Packages the Python backend for Windows x64 standalone builds.
#>
param()

$ErrorActionPreference = "Stop"

$PythonStandaloneTag = "20260325"
$PythonVersion = "3.12.13"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$OutputDir = Join-Path $RepoRoot "build\resources\backend"

$PbsTarball = "cpython-$PythonVersion+$PythonStandaloneTag-x86_64-pc-windows-msvc-install_only.tar.gz"
$PbsUrl = "https://github.com/indygreg/python-build-standalone/releases/download/$PythonStandaloneTag/$PbsTarball"

Write-Host "=== Packaging backend for Windows x64 ==="
Write-Host "    Python: $PythonVersion"
Write-Host "    Output: $OutputDir"

if (Test-Path $OutputDir) { Remove-Item -Recurse -Force $OutputDir }
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$DownloadDir = Join-Path $RepoRoot "build\.cache\python-standalone"
New-Item -ItemType Directory -Force -Path $DownloadDir | Out-Null
$TarballPath = Join-Path $DownloadDir $PbsTarball

if (-not (Test-Path $TarballPath)) {
    Write-Host "--- Downloading standalone Python ---"
    Write-Host "    URL: $PbsUrl"
    Invoke-WebRequest -Uri $PbsUrl -OutFile $TarballPath -UseBasicParsing
} else {
    Write-Host "--- Using cached standalone Python ---"
}

$ExtractDir = Join-Path $RepoRoot "build\.staging\backend-win-x64"
if (Test-Path $ExtractDir) { Remove-Item -Recurse -Force $ExtractDir }
New-Item -ItemType Directory -Force -Path $ExtractDir | Out-Null

Write-Host "--- Extracting standalone Python ---"
tar -xzf $TarballPath -C $ExtractDir

$PythonPrefix = Get-ChildItem -Path $ExtractDir -Directory -Filter "python*" | Select-Object -First 1
if (-not $PythonPrefix) {
    Write-Host "ERROR: Could not find extracted python directory"
    exit 1
}
Write-Host "    Extracted to: $($PythonPrefix.FullName)"

Write-Host "--- Staging Python runtime ---"
Copy-Item -Path (Join-Path $PythonPrefix.FullName "python.exe") -Destination (Join-Path $OutputDir "python.exe")
Copy-Item -Path (Join-Path $PythonPrefix.FullName "python3.exe") -Destination (Join-Path $OutputDir "python3.exe") -ErrorAction SilentlyContinue
Copy-Item -Path (Join-Path $PythonPrefix.FullName "pythonw.exe") -Destination (Join-Path $OutputDir "pythonw.exe") -ErrorAction SilentlyContinue

# Copy top-level DLLs (python312.dll, python3.dll, vcruntime140.dll, etc.)
$TopLevelDlls = Get-ChildItem -Path $PythonPrefix.FullName -Filter "*.dll" -File
if ($TopLevelDlls) {
    Copy-Item -Path $TopLevelDlls.FullName -Destination $OutputDir
    Write-Host "    Copied $($TopLevelDlls.Count) DLLs: $($TopLevelDlls.Name -join ', ')"
} else {
    Write-Host "    WARNING: No top-level DLLs found in $($PythonPrefix.FullName)"
}

$LibDir = Join-Path $PythonPrefix.FullName "Lib"
if (Test-Path $LibDir) {
    Copy-Item -Recurse -Path $LibDir -Destination (Join-Path $OutputDir "Lib")
}

$DllsDir = Join-Path $PythonPrefix.FullName "DLLs"
if (Test-Path $DllsDir) {
    Copy-Item -Recurse -Path $DllsDir -Destination (Join-Path $OutputDir "DLLs") -ErrorAction SilentlyContinue
}

Write-Host "--- Copying backend source ---"
$AppDir = Join-Path $OutputDir "app"
New-Item -ItemType Directory -Force -Path $AppDir | Out-Null
Copy-Item -Recurse -Path (Join-Path $RepoRoot "src\python") -Destination (Join-Path $AppDir "src\python")

Write-Host "--- Installing dependencies from pyproject.toml ---"
$StagedPython = Join-Path $OutputDir "python.exe"
if (-not (Test-Path $StagedPython)) {
    Write-Host "ERROR: Staged python.exe not found at $StagedPython"
    exit 1
}

$SitePackagesDir = Join-Path $OutputDir "Lib\site-packages"
New-Item -ItemType Directory -Force -Path $SitePackagesDir | Out-Null

& $StagedPython -m pip install --no-cache-dir --no-compile "--target=$SitePackagesDir" $RepoRoot

Write-Host "--- Verifying stdlib imports ---"
$env:PYTHONPATH = "$SitePackagesDir;$AppDir\src\python"
& $StagedPython -c @"
import os, sys, json
print(f'Python: {sys.version}')
print(f'prefix: {sys.prefix}')
print(f'os from: {os.__file__}')
assert 'Lib' in os.__file__, f'stdlib not in staged Lib: {os.__file__}'
print('stdlib: OK')
"@

Write-Host "--- Verifying third-party imports ---"
& $StagedPython -c @"
import fastapi, uvicorn, chromadb
print(f'fastapi {fastapi.__version__}')
print(f'uvicorn {uvicorn.__version__}')
print(f'chromadb {chromadb.__version__}')
print('third-party deps: OK')
"@

Write-Host "--- Verifying backend code imports ---"
& $StagedPython -c @"
import main
print('backend code: OK')
"@

Write-Host "--- Cleaning temp artifacts ---"
if (Test-Path $ExtractDir) { Remove-Item -Recurse -Force $ExtractDir }

$ChromaOutput = Join-Path $RepoRoot "build\resources\data\chroma_db"

if ($env:PERSONAL_BUILD -ne "1") {
  Write-Host "--- Pre-building ChromaDB index from bundled CMGs ---"
  if (Test-Path $ChromaOutput) { Remove-Item -Recurse -Force $ChromaOutput }
  New-Item -ItemType Directory -Force -Path $ChromaOutput | Out-Null
  & $StagedPython -c @"
import sys
sys.path.insert(0, '$SitePackagesDir')
sys.path.insert(0, '$AppDir\src\python')
from pipeline.actas.chunker import chunk_and_ingest
chunk_and_ingest(structured_dir=r'$RepoRoot\data\cmgs\structured', db_path=r'$ChromaOutput')
import chromadb
client = chromadb.PersistentClient(path=r'$ChromaOutput')
col = client.get_or_create_collection('guidelines_actas')
print(f'Pre-built index: {col.count()} chunks')
"@
} else {
  Write-Host "--- Personal build: using pre-built ChromaDB ---"
  if (-not (Test-Path $ChromaOutput)) {
    Write-Host "ERROR: PERSONAL_BUILD=1 but no pre-built ChromaDB at $ChromaOutput"
    exit 1
  }
  Write-Host "    Found pre-built ChromaDB at $ChromaOutput"
}

Write-Host "=== Backend payload ready at $OutputDir ==="
