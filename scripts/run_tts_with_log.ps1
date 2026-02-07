param(
    [Parameter(Mandatory = $true)]
    [string]$LogPath
)

$ErrorActionPreference = "Continue"
Start-Transcript -Path $LogPath -Append | Out-Null
try {
    # Show TTS output in the console while transcript persists it to file.
    & ".\venv\Scripts\python.exe" ".\server_fastapi.py"
}
finally {
    Stop-Transcript | Out-Null
}
