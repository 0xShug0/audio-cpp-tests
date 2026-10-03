param([Parameter(Mandatory)][ValidateSet('before', 'after')][string]$Stage)
$ErrorActionPreference = 'Stop'
(& "$env:CONDA/Scripts/conda.exe" shell.powershell hook) | Out-String | Invoke-Expression
conda activate qwen3-tts
if ($LASTEXITCODE) { throw 'Conda activation failed' }
$root = $PSScriptRoot
$artifacts = Join-Path $root 'artifacts'
$binary = Get-ChildItem (Join-Path $root 'audio.cpp/build/debug') -Filter audiocpp_server.exe -Recurse
if (@($binary).Count -ne 1) { throw 'Expected exactly one server executable' }
$chinese = -join @([char]0x6D4B, [char]0x8BD5, [char]0x76EE, [char]0x5F55)
foreach ($case in @('ascii', 'unicode')) {
    $name = if ($case -eq 'unicode') { $chinese } else { 'ascii' }
    $dir = Join-Path $artifacts "$Stage/$name"
    New-Item -ItemType Directory $dir -Force | Out-Null
    Copy-Item $binary.FullName "$dir/audiocpp_server.exe"
    Get-ChildItem $binary.Directory -Filter *.dll | Copy-Item -Destination $dir
    Copy-Item "$artifacts/model.gguf" "$dir/model.gguf"
    Copy-Item "$root/audio.cpp/assets/resources/sample_16k.wav" "$dir/input.wav"
    $config = @{
        host = '127.0.0.1'; port = 18069; backend = 'cpu'; threads = 2; lazy_load = $false
        models = @(@{id = 'vad'; family = 'pulsevad'; task = 'vad'; mode = 'offline'; path = "$dir/model.gguf"})
    }
    $configPath = "$artifacts/$Stage-$case-config.json"
    $logPath = "$artifacts/$Stage-$case-server.log"
    $config | ConvertTo-Json -Depth 6 | Set-Content $configPath -Encoding utf8NoBOM
    $info = [Diagnostics.ProcessStartInfo]::new("$dir/audiocpp_server.exe")
    $info.WorkingDirectory = $dir
    $info.UseShellExecute = $false
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    foreach ($arg in @('--config', $configPath, '--log', '--log-file', $logPath)) {
        $info.ArgumentList.Add($arg)
    }
    $process = [Diagnostics.Process]::Start($info)
    $stdout = $process.StandardOutput.ReadToEndAsync()
    $stderr = $process.StandardError.ReadToEndAsync()
    try {
        $ready = $false
        for ($i = 0; $i -lt 120; ++$i) {
            if ($process.HasExited) { break }
            try {
                $models = Invoke-RestMethod http://127.0.0.1:18069/v1/models -TimeoutSec 2
                if ($models.data[0].loaded) { $ready = $true; break }
            } catch [System.Net.Http.HttpRequestException] {
                # Startup polling only; failure after the deadline is an error.
            }
            Start-Sleep -Milliseconds 500
        }
        if ($Stage -eq 'before' -and $case -eq 'unicode') {
            if ($ready -or !$process.HasExited -or $process.ExitCode -eq 0) {
                throw 'Expected baseline Unicode path startup failure was not reproduced'
            }
            $errorText = $stderr.GetAwaiter().GetResult()
            if ($errorText -notmatch 'model path does not exist|filesystem error|failed to open|cannot open') {
                throw "Baseline failed for an unexpected reason: $errorText"
            }
            Write-Host 'Confirmed baseline Unicode path failure'
        } else {
            if (!$ready) { throw 'Server did not load the model' }
            $models | ConvertTo-Json -Depth 10 | Set-Content "$dir/models.json"
            $body = @{model = 'vad'; request = @{audio = "$dir/input.wav"}} | ConvertTo-Json -Depth 5 -Compress
            $body | Set-Content "$dir/request.json" -Encoding utf8NoBOM
            $response = Invoke-WebRequest http://127.0.0.1:18069/v1/tasks/run -Method Post -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($body)) -TimeoutSec 120
            $response.Content | Set-Content "$dir/response.json" -Encoding utf8NoBOM
            Write-Host "$Stage $case inference: $($response.Content)"
        }
    } finally {
        if (!$process.HasExited) { $process.Kill($true) }
        $process.WaitForExit()
        $stdout.GetAwaiter().GetResult() | Set-Content "$dir/stdout.log"
        $stderr.GetAwaiter().GetResult() | Set-Content "$dir/stderr.log"
    }
}
if ($Stage -eq 'after') {
    $responses = @("$artifacts/before/ascii/response.json", "$artifacts/after/ascii/response.json", "$artifacts/after/$chinese/response.json")
    $reference = $null
    foreach ($file in $responses) {
        $result = Get-Content $file -Raw | ConvertFrom-Json -AsHashtable
        # Exclude timing only; every semantic result field must match.
        $result.Remove('timing')
        $json = ConvertTo-Json -InputObject $result -Depth 30 -Compress
        if ($null -eq $reference) { $reference = $json }
        elseif ($json -cne $reference) { throw "Output mismatch: $file" }
    }
    'PASS: baseline Unicode failure reproduced; patched ASCII and Unicode outputs match baseline ASCII.' | Tee-Object "$artifacts/result.txt"
}
