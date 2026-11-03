# Lancia un worker dsh headless su un brief.
#
#   .\orchestration\run-worker.ps1 -Model 37 -Brief F01 -AutoApprove
#
# Il worker gira con cwd = <WORKSPACE>/, che e' anche la sua workspace root:
# non puo' scrivere fuori da li'. Il brief viene COPIATO nella workspace come
# BRIEF-<nome>.md e il worker riceve solo l'istruzione di leggerlo: cosi' il
# testo del brief non passa mai attraverso l'interpolazione di PowerShell
# (backtick e ${...} lo corromperebbero).
#
# ADATTA: sostituisci "<WORKSPACE>" con la cartella sandbox del tuo progetto
# (dove vive AGENTS.md e dove il worker puo' scrivere).

param(
    [Parameter(Mandatory = $true)][string]$Model,
    [Parameter(Mandatory = $true)][string]$Brief,
    [switch]$AutoApprove
)

$ErrorActionPreference = 'Stop'

$root      = Split-Path -Parent $PSScriptRoot
$workspace = Join-Path $root '<WORKSPACE>'
$patchDir  = Join-Path $root 'orchestration\dsh'
$briefPath = Join-Path $root "orchestration\briefs\$Brief.md"
$reportDir = Join-Path $root 'orchestration\reports'
$briefDest = Join-Path $workspace "BRIEF-$Brief.md"

if (-not (Test-Path $briefPath)) { throw "brief non trovato: $briefPath" }
if (-not (Test-Path $reportDir)) { New-Item -ItemType Directory -Path $reportDir | Out-Null }

Copy-Item $briefPath $briefDest -Force

# Prompt minimo e privo di metacaratteri: il contenuto vero sta nel brief.
$briefName = "BRIEF-$Brief.md"
$task = 'Leggi AGENTS.md e poi ' + $briefName + ' in questa cartella. ' + $briefName + ' contiene il task da eseguire: seguilo alla lettera, scrivendo esclusivamente i file elencati nella sua sezione FILE CHE SCRIVI. Non modificarlo. Chiudi con il blocco REPORT richiesto da AGENTS.md.'

# base.yml = approvazione automatica dentro la sandbox workspace-write.
# probe.yml = solo permessi di serie (approvazione richiesta) -- utile per un
# primo giro di prova prima di fidarsi del brief.
$permPatch = if ($AutoApprove) { 'base.yml' } else { 'probe.yml' }

$dsh = Join-Path $env:APPDATA 'npm\dsh.cmd'
$log = Join-Path $reportDir "$Brief-$Model.log"

Push-Location $workspace
try {
    & $dsh --profile headless `
        --patch (Join-Path $patchDir $permPatch) `
        --patch (Join-Path $patchDir "model-$Model.yml") `
        $task 2>&1 | Tee-Object -FilePath $log
}
finally {
    Pop-Location
    if (Test-Path $briefDest) { Remove-Item $briefDest -Force }
}

Write-Host ""
Write-Host "log: $log"
