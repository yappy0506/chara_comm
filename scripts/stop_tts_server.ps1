param()

$ErrorActionPreference = "SilentlyContinue"

$venvPython = Join-Path (Resolve-Path ".\Style-Bert-VITS2-2.7.0").Path "venv\Scripts\python.exe"
$n = 0
Get-Process python |
    Where-Object { $_.Path -eq $venvPython } |
    ForEach-Object {
        try {
            Stop-Process -Id $_.Id -Force -ErrorAction Stop
            $n++
        } catch {
        }
    }
