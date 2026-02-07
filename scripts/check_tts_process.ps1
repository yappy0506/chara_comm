param()

$ErrorActionPreference = "SilentlyContinue"

$venvPython = Join-Path (Resolve-Path ".\Style-Bert-VITS2-2.7.0").Path "venv\Scripts\python.exe"
$procs = Get-Process python | Where-Object { $_.Path -eq $venvPython }
if ($procs) {
    exit 0
}
exit 1
