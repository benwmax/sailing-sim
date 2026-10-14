# Runs the automation tests headless (no window, no GPU) and writes a report. Windows twin of scripts/test.sh.
# Usage: scripts\windows\test.ps1 [-Filter SailingSim]
#   Report: Artifacts\TestReport\index.json   Log: Artifacts\test.log
# Always build first (scripts\windows\build.ps1): the editor loads the DLLs in Binaries\Win64, it does not compile.
param([string]$Filter = 'SailingSim')
. (Join-Path $PSScriptRoot 'env.ps1')

$ReportDir = Join-Path $Artifacts 'TestReport'
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $ReportDir
New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null

$ArgLine = "`"$Project`" -ExecCmds=`"Automation RunTests $Filter; Quit`" -TestExit=`"Automation Test Queue Empty`" " +
	"-ReportExportPath=`"$ReportDir`" -unattended -nullrhi -nosplash -nosound -NoP4 -stdout -FullStdOutLogOutput"
Write-Host "Running tests '$Filter' headless (a few minutes; the first run on a PC also compiles shaders)..."
# The editor's own output is long; it goes to the log only. Progress: Get-Content -Wait Artifacts\test.log
$Log = Join-Path $Artifacts 'test.log'
$P = Start-Process -FilePath $EditorCmd -ArgumentList $ArgLine -NoNewWindow -PassThru -RedirectStandardOutput $Log -RedirectStandardError "$Log.stderr"
$null = $P.Handle
$P.WaitForExit()
$EditorExit = $P.ExitCode
if (Test-Path "$Log.stderr") { Get-Content "$Log.stderr" | Add-Content $Log; Remove-Item -Force "$Log.stderr" }

$Index = Join-Path $ReportDir 'index.json'
if (-not (Test-Path $Index)) {
	Write-Host "No test report written; see Artifacts\test.log" -ForegroundColor Red
	exit 2
}
$Report = Get-Content -Raw -Encoding UTF8 $Index | ConvertFrom-Json
$Tests = @($Report.tests)
foreach ($T in $Tests) {
	Write-Host ('{0,-8} {1}' -f $T.state, $T.fullTestPath)
	foreach ($E in @($T.entries)) {
		if ($E.event.type -eq 'Error') { Write-Host "         ! $($E.event.message)" -ForegroundColor Red }
	}
}
# Warnings (for example the editor's own network probe timing out during a long test) do not fail a test.
$Passed = [int]$Report.succeeded + [int]$Report.succeededWithWarnings
$Failed = [int]$Report.failed
Write-Host ""
Write-Host "$Passed passed, $Failed failed, $($Tests.Count) total"
if ($Failed -gt 0 -or $Tests.Count -eq 0 -or $EditorExit -ne 0) {
	Write-Host "Tests failed (editor exit $EditorExit). See Artifacts\test.log" -ForegroundColor Red
	exit 1
}
exit 0
