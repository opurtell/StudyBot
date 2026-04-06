<#
.SYNOPSIS
    Verifies the staged backend payload for Windows x64 builds.
#>
param()

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$PayloadDir = Join-Path $RepoRoot "build\resources\backend"

Write-Host "=== Verifying backend payload ==="

$errors = 0

if (-not (Test-Path $PayloadDir)) {
    Write-Host "FAIL: Payload directory missing: $PayloadDir"
    exit 1
}

$PythonExe = Join-Path $PayloadDir "python.exe"
if (-not (Test-Path $PythonExe)) {
    Write-Host "FAIL: python.exe not found: $PythonExe"
    $errors++
} else {
    Write-Host "OK:   python.exe found"
}

$LibDir = Join-Path $PayloadDir "Lib"
if (-not (Test-Path $LibDir)) {
    Write-Host "FAIL: Lib/ directory missing"
    $errors++
} else {
    Write-Host "OK:   Lib/ directory exists"
}

$AppDir = Join-Path $PayloadDir "app\src\python"
if (-not (Test-Path $AppDir)) {
    Write-Host "FAIL: Backend source missing: app\src\python\"
    $errors++
} else {
    Write-Host "OK:   Backend source present"
}

if ($errors -gt 0) {
    Write-Host "=== Skipping import checks ($errors structural errors) ==="
    exit 1
}

$SitePackagesDir = Join-Path $PayloadDir "Lib\site-packages"
$env:PYTHONPATH = "$SitePackagesDir;$AppDir"

Write-Host "--- Checking stdlib imports ---"
& $PythonExe -c @"
import os, sys, json
assert 'Lib' in os.__file__, f'stdlib not from staged Lib: {os.__file__}'
print('OK:   stdlib imports work')
"@
if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: stdlib imports failed"; exit 1 }

Write-Host "--- Checking third-party imports ---"
& $PythonExe -c @"
import fastapi, uvicorn, chromadb
print('OK:   third-party imports work')
"@
if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: third-party imports failed"; exit 1 }

Write-Host "--- Checking backend code imports ---"
& $PythonExe -c @"
import main
print('OK:   backend code imports work')
"@
if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: backend code imports failed"; exit 1 }

Write-Host "=== All checks passed ==="
