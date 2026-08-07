param(
    [string]$VoiceName = "Microsoft Heami Desktop",
    [int]$Rate = 0
)

$ErrorActionPreference = "Stop"

$evaluationRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$manifestPath = Join-Path $evaluationRoot "samples\validation_samples.json"
$manifest = Get-Content -Raw -Encoding UTF8 -LiteralPath $manifestPath | ConvertFrom-Json
$speaker = New-Object -ComObject SAPI.SpVoice
$matchingVoices = @($speaker.GetVoices() | Where-Object { $_.GetDescription() -like "$VoiceName*" })

if ($matchingVoices.Count -eq 0) {
    $availableVoices = @($speaker.GetVoices() | ForEach-Object { $_.GetDescription() }) -join ", "
    throw "Voice '$VoiceName' is not installed. Available voices: $availableVoices"
}

$speaker.Voice = $matchingVoices[0]
$speaker.Rate = $Rate
$speaker.AllowAudioOutputFormatChangesOnNextSet = $true

foreach ($sample in $manifest.samples) {
    if ($sample.audio.kind -ne "tts") {
        continue
    }

    $outputPath = Join-Path $evaluationRoot $sample.audio.path
    $outputDirectory = Split-Path -Parent $outputPath
    New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null

    $stream = New-Object -ComObject SAPI.SpFileStream
    try {
        $stream.Open($outputPath, 3, $false)
        $speaker.AudioOutputStream = $stream
        [void]$speaker.Speak($sample.transcript)
    }
    finally {
        $stream.Close()
        $speaker.AudioOutputStream = $null
    }

    Write-Output $outputPath
}
