# Lancia un worker dsh headless su un brief.
#
#   .\orchestration\run-worker.ps1 -Model 37 -Brief F01 -AutoApprove
#
# Il worker gira con cwd = <WORKSPACE>/, che e' anche la sua workspace root:
# non puo' scrivere fuori da li'. Ogni run crea una copia temporanea esclusiva
# del brief nella workspace e il worker riceve solo l'istruzione di leggerla:
# il testo non passa attraverso l'interpolazione di PowerShell (backtick e
# ${...} lo corromperebbero). Il run rimuove soltanto la propria copia.
#
# ADATTA: sostituisci "<WORKSPACE>" con la cartella sandbox del tuo progetto
# (dove vive AGENTS.md e dove il worker puo' scrivere).

param(
    [Parameter(Mandatory = $true)][string]$Model,
    [Parameter(Mandatory = $true)][string]$Brief,
    [switch]$AutoApprove
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false

$root      = Split-Path -Parent $PSScriptRoot
$workspace = Join-Path $root '<WORKSPACE>'
$patchDir  = Join-Path $root 'orchestration\dsh'
$briefPath = Join-Path $root "orchestration\briefs\$Brief.md"
$reportDir = Join-Path $root 'orchestration\reports'
$runId     = [guid]::NewGuid().ToString('N')
$briefName = "BRIEF-$runId.md"
$briefDest = Join-Path $workspace $briefName
$log       = Join-Path $reportDir "$Brief-$Model-$runId.log"

if (-not (Test-Path -LiteralPath $briefPath -PathType Leaf)) { throw "brief non trovato: $briefPath" }
[System.IO.Directory]::CreateDirectory($reportDir) | Out-Null

# Prompt minimo e privo di metacaratteri: il contenuto vero sta nel brief.
$task = 'Leggi AGENTS.md e poi ' + $briefName + ' in questa cartella. ' + $briefName + ' contiene il task da eseguire: seguilo alla lettera, scrivendo esclusivamente i file elencati nella sua sezione FILE CHE SCRIVI. Non modificarlo. Chiudi con il blocco REPORT richiesto da AGENTS.md.'

# base.yml = approvazione automatica dentro la sandbox workspace-write.
# probe.yml = solo permessi di serie (approvazione richiesta) -- utile per un
# primo giro di prova prima di fidarsi del brief.
$permPatch = if ($AutoApprove) { 'base.yml' } else { 'probe.yml' }
$dsh = Join-Path $env:APPDATA 'npm\dsh.cmd'

$briefStream = $null
$ownsBrief = $false
$logStream = $null
$logWriter = $null
$locationPushed = $false
$launchError = $null
$cleanupError = $null
$workerExitCode = $null
try {
    $briefBytes = [System.IO.File]::ReadAllBytes($briefPath)
    # CreateNew non sovrascrive mai file esistenti. Dopo la scrittura, un
    # handle di sola lettura consente ai normali lettori di aprire il brief
    # e impedisce la sostituzione mentre il worker e' attivo su Windows.
    $briefStream = [System.IO.FileStream]::new($briefDest, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
    $ownsBrief = $true
    $briefStream.Write($briefBytes, 0, $briefBytes.Length)
    $briefStream.Dispose()
    $briefStream = $null
    $briefStream = [System.IO.File]::Open($briefDest, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::Read)

    # Il transcript e' un risultato da conservare, non un temporaneo.
    $logStream = [System.IO.FileStream]::new($log, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::Read)
    $logWriter = [System.IO.StreamWriter]::new($logStream, [System.Text.UTF8Encoding]::new($false))
    $logWriter.AutoFlush = $true

    Push-Location -LiteralPath $workspace
    $locationPushed = $true
    $previousErrorAction = $ErrorActionPreference
    try {
        # Windows PowerShell 5.1 tratta stderr nativo come errore: non deve
        # interrompere lo stream ne' nascondere il vero codice del worker.
        $ErrorActionPreference = 'Continue'
        $LASTEXITCODE = $null
        & $dsh --profile headless `
            --patch (Join-Path $patchDir $permPatch) `
            --patch (Join-Path $patchDir "model-$Model.yml") `
            $task 2>&1 | ForEach-Object {
                # Keep log-write failures terminating without treating native
                # stderr as an exception in the surrounding pipeline.
                & {
                    param($record)
                    $ErrorActionPreference = 'Stop'
                    $line = $record.ToString()
                    $logWriter.WriteLine($line)
                    Write-Output $line
                } $_
            }
        $workerExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorAction
    }
    if ($null -eq $workerExitCode) { throw "worker non avviato: $dsh" }
}
catch {
    $launchError = $_
}
finally {
    if ($locationPushed) {
        try { Pop-Location }
        catch { $cleanupError = $_; Write-Warning "Impossibile ripristinare la directory: $_" }
    }
    if ($logWriter -or $logStream) {
        try {
            if ($logWriter) { $logWriter.Dispose() } else { $logStream.Dispose() }
        }
        catch { if (-not $cleanupError) { $cleanupError = $_ }; Write-Warning "Impossibile chiudere il log ${log}: $_" }
    }
    if ($ownsBrief) {
        try {
            if ($briefStream) { $briefStream.Dispose() }
            [System.IO.File]::Delete($briefDest)
        }
        catch { if (-not $cleanupError) { $cleanupError = $_ }; Write-Warning "Impossibile rimuovere il brief temporaneo ${briefDest}: $_" }
    }
}

if ($logStream) {
    Write-Host ""
    Write-Host "log: $log"
}
if ($launchError) { throw $launchError }
if ($workerExitCode -ne 0) { exit $workerExitCode }
if ($cleanupError) { throw $cleanupError }
