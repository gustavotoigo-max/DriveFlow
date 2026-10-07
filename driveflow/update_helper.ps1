param([Parameter(Mandatory=$true)][string]$JobFile)
$ErrorActionPreference = 'Stop'
$job = Get-Content -LiteralPath $JobFile -Raw | ConvertFrom-Json
$log = Join-Path (Split-Path -Parent $JobFile) 'result.txt'
$pending = $job.target + '.update-pending'
$backup = $job.target + '.update-backup'
$replaced = $false
try {
    # Wait only for the old process; never terminate an upload worker.
    $oldProcess = Get-Process -Id $job.pid -ErrorAction SilentlyContinue
    if ($oldProcess -and -not $oldProcess.WaitForExit(120000)) { throw 'O aplicativo anterior nao encerrou.' }
    $stream = [System.IO.File]::OpenRead($job.source)
    $hasher = [System.Security.Cryptography.SHA256]::Create()
    try { $digest = [BitConverter]::ToString($hasher.ComputeHash($stream)).Replace('-', '').ToLower() }
    finally { $stream.Dispose(); $hasher.Dispose() }
    if ($digest -ne $job.sha256) { throw 'SHA-256 invalido.' }
    # Validate that the staged executable starts before replacing the installed one.
    $smoke = Join-Path (Split-Path -Parent $JobFile) 'smoke.json'
    $check = Start-Process -FilePath $job.source -ArgumentList ('--smoke-test "' + $smoke + '"') -WindowStyle Hidden -PassThru
    if (-not $check.WaitForExit(60000)) { $check.Kill(); throw 'Teste da nova versao excedeu o prazo.' }
    if ($check.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $smoke)) { throw 'Nova versao nao iniciou.' }
    $result = Get-Content -LiteralPath $smoke -Raw | ConvertFrom-Json
    if (-not $result.ok -or $result.version -ne $job.version -or -not $result.monitoring_dependencies) { throw 'Teste da nova versao falhou.' }
    Copy-Item -LiteralPath $job.source -Destination $pending -Force
    # One-file PyInstaller has an outer process that may release the file a little later.
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        try { [System.IO.File]::Replace($pending, $job.target, $backup, $true); $replaced = $true; break }
        catch { if ($attempt -eq 59) { throw }; Start-Sleep -Seconds 1 }
    }
    Start-Process -FilePath $job.target -WorkingDirectory (Split-Path -Parent $job.target)
    'Atualizacao instalada.' | Set-Content -LiteralPath $log -Encoding UTF8
} catch {
    if ($replaced) { [System.IO.File]::Replace($backup, $job.target, $null, $true) }
    ('Atualizacao nao aplicada: ' + $_.Exception.Message) | Set-Content -LiteralPath $log -Encoding UTF8
    # The previous executable is retained on failure and can still be opened manually.
    if (Test-Path -LiteralPath $job.target) { Start-Process -FilePath $job.target -WorkingDirectory (Split-Path -Parent $job.target) }
}
