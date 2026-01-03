param(
  [string]$AppPath = "app\main.py"
)

Write-Host "== D&D Encounter Builder ==" -ForegroundColor Cyan
Write-Host "Working dir: $(Get-Location)"
Write-Host "App path: $AppPath"

if (-not (Test-Path $AppPath)) {
  throw "App file not found: $AppPath"
}

Write-Host "`n[1/2] Syntax check (py_compile)..." -ForegroundColor Yellow
python -m py_compile $AppPath
if ($LASTEXITCODE -ne 0) { throw "Syntax check failed. Fix before running." }

Write-Host "`n[2/2] Starting Streamlit..." -ForegroundColor Yellow
streamlit run $AppPath
