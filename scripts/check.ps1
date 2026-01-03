param(
  [string]$AppPath = "app\main.py"
)

if (-not (Test-Path $AppPath)) {
  throw "App file not found: $AppPath"
}

Write-Host "[A] Syntax check (py_compile)..." -ForegroundColor Yellow
python -m py_compile $AppPath
if ($LASTEXITCODE -ne 0) { throw "Syntax check failed." }

Write-Host "[B] Guardrails..." -ForegroundColor Yellow

# Hard rule: do not reintroduce browser printing
$bad = Select-String -Path $AppPath -Pattern "window\.print\(|st\.components\.v1\.html\(|@media\s+print|print\(" -SimpleMatch -ErrorAction SilentlyContinue
if ($bad) {
  Write-Host "FOUND forbidden printing-related strings:" -ForegroundColor Red
  $bad | ForEach-Object { Write-Host $_.LineNumber ":" $_.Line }
  throw "Guardrail failed: printing-related code detected."
}

Write-Host "OK: checks passed." -ForegroundColor Green
