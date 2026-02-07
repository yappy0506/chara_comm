param(
    [Parameter(Mandatory = $true)]
    [string]$BaseUrl
)

$ErrorActionPreference = "Stop"

$base = $BaseUrl.TrimEnd("/")

try {
    $modelsResp = Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 -Uri "$base/models/info"
    if ($modelsResp.StatusCode -ne 200) {
        Write-Output "[DEBUG] TTS readiness: /models/info status=$($modelsResp.StatusCode)"
        exit 1
    }
    $models = $modelsResp.Content | ConvertFrom-Json
    if (-not $models) {
        Write-Output "[DEBUG] TTS readiness: /models/info returned empty payload."
        exit 1
    }
    if (-not $models.PSObject.Properties.Name -or $models.PSObject.Properties.Name.Count -lt 1) {
        Write-Output "[DEBUG] TTS readiness: no models loaded."
        exit 1
    }
} catch {
    Write-Output "[DEBUG] TTS readiness: /models/info failed: $($_.Exception.Message)"
    exit 1
}

try {
    $modelIds = @($models.PSObject.Properties.Name | Sort-Object)
    $modelId = $modelIds[0]
    $modelInfo = $models.PSObject.Properties[$modelId].Value

    $speakerId = 0
    if ($modelInfo -and $modelInfo.id2spk) {
        $speakerIds = @($modelInfo.id2spk.PSObject.Properties.Name | Sort-Object)
        if ($speakerIds.Count -gt 0) {
            $speakerId = $speakerIds[0]
        }
    }

    $styleQuery = ""
    if ($modelInfo -and $modelInfo.style2id) {
        $styles = @($modelInfo.style2id.PSObject.Properties.Name)
        if ($styles.Count -gt 0) {
            $encodedStyle = [System.Uri]::EscapeDataString($styles[0])
            $styleQuery = "&style=$encodedStyle"
        }
    }

    $voiceUri = "$base/voice?text=test&model_id=$modelId&speaker_id=$speakerId&auto_split=false$styleQuery"
    $voiceResp = Invoke-WebRequest -UseBasicParsing -Method POST -TimeoutSec 8 -Uri $voiceUri
    if ($voiceResp.StatusCode -ne 200) {
        Write-Output "[DEBUG] TTS readiness: /voice status=$($voiceResp.StatusCode)"
        exit 1
    }
    $contentType = "" + $voiceResp.Headers["Content-Type"]
    if ($contentType -notmatch "audio/wav") {
        Write-Output "[DEBUG] TTS readiness: /voice content-type=$contentType"
        exit 1
    }
    if ($voiceResp.RawContentLength -le 44) {
        Write-Output "[DEBUG] TTS readiness: /voice returned too-short payload."
        exit 1
    }
} catch {
    Write-Output "[DEBUG] TTS readiness: /voice failed: $($_.Exception.Message)"
    exit 1
}

exit 0
