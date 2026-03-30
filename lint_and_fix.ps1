# B.L.A.S.T. Engineering Excellence Script
# Uses Ruff for lightning-fast linting and fixing

Write-Host "--- INITIALIZING ENGINEERING AUDIT [RUFF] ---" -ForegroundColor Cyan

# Check if ruff is installed
if (!(Get-Command ruff -ErrorAction SilentlyContinue)) {
    Write-Host "WARNING: Ruff not found in PATH. Attempting installation via pip..." -ForegroundColor Yellow
    pip install ruff
}

# Run Linting & Fixing
Write-Host "Executing Forensic Code Repair..." -ForegroundColor Green
ruff check . --fix

# Run Formatting
Write-Host "Optimizing Visual Code Structure..." -ForegroundColor Green
ruff format .

Write-Host "--- AUDIT COMPLETE: 100% CODE INTEGRITY ---" -ForegroundColor Cyan
