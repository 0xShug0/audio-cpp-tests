$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$cli = (Get-ChildItem prebuilt -Filter audiocpp_cli.exe -Recurse | Select-Object -First 1).FullName
if (!$cli) { throw 'Published archive does not contain audiocpp_cli.exe' }
$ttsModel = (Resolve-Path models/tts.gguf).Path
$asrModel = (Resolve-Path models/asr.gguf).Path
$reference = (Resolve-Path artifacts/reference.wav).Path
$output = Join-Path (Resolve-Path artifacts).Path 'tts-cpu.wav'
$cases = @(
    @{
        Name = 'tts-cpu'
        Arguments = @('--task', 'tts', '--family', 'qwen3_tts', '--model', $ttsModel,
            '--backend', 'cpu', '--text', 'Test.', '--out', $output, '--language', 'French',
            '--voice-ref', $reference, '--reference-text', 'Ceci est un test de ma voix.', '--log')
    },
    @{
        Name = 'asr-cpu-control'
        Arguments = @('--task', 'asr', '--family', 'qwen3_asr', '--model', $asrModel,
            '--backend', 'cpu', '--audio', $reference, '--language', 'English', '--log')
    }
)
$results = @()
foreach ($case in $cases) {
    $name = $case.Name
    $arguments = $case.Arguments
    @{ executable = $cli; arguments = $arguments } | ConvertTo-Json -Depth 5 |
        Set-Content "artifacts/$name-command.json"
    & $cli @arguments 2>&1 | Tee-Object "artifacts/$name.log"
    $code = $LASTEXITCODE
    $hex = '0x{0:X8}' -f ([long]$code -band 0xffffffffL)
    $results += @{ name = $name; exit_code = $code; exit_hex = $hex }
    $results | ConvertTo-Json -Depth 5 | Set-Content artifacts/results.json
    if ($code -ne 0) {
        $dumps = New-Item -ItemType Directory "artifacts/$name-dumps" -Force
        & ./diagnostics/procdump64.exe -accepteula -e -mm -x $dumps.FullName $cli @arguments 2>&1 |
            Tee-Object "artifacts/$name-procdump.log"
        "ProcDump exit code: $LASTEXITCODE" | Add-Content "artifacts/$name-procdump.log"
    }
}
Get-ChildItem artifacts -Filter '*.wav' | Get-FileHash -Algorithm SHA256 |
    Format-List | Out-File artifacts/wav-sha256.txt
if (($results | Where-Object { $_.exit_code -ne 0 }).Count -gt 0) {
    throw 'One or more requests failed'
}
if (!(Test-Path $output) -or (Get-Item $output).Length -le 44) {
    throw 'TTS returned success without a nonempty WAV'
}
