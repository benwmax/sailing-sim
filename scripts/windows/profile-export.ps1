# Exports CPU timer statistics from an Unreal Insights trace (.utrace), headless, as CSV per thread group.
# Capture first, e.g.: scripts\windows\bench-win.ps1 -Quality Ultra -Demo -GameArgs "<view args> -trace=cpu,frame,gpu,bookmark -statnamedevents -tracefile=C:\path\view.utrace"
# Usage: scripts\windows\profile-export.ps1 -Trace Artifacts\prof\beam8.utrace [-Threads GameThread,RenderThread,RHIThread]
#   Writes <trace>.<thread>.csv next to the trace (Insights' timer statistics: count, inclusive and exclusive times).
param(
	[Parameter(Mandatory = $true)][string]$Trace,
	[string[]]$Threads = @('GameThread', 'RenderThread', 'RHIThread', 'Foreground Worker*', 'Background Worker*')
)
. (Join-Path $PSScriptRoot 'env.ps1')
$Insights = Join-Path $UERoot 'Engine\Binaries\Win64\UnrealInsights.exe'
$Trace = (Resolve-Path $Trace).Path
$Threads = @($Threads | ForEach-Object { $_ -split ',' } | Where-Object { $_ })
$Base = [System.IO.Path]::ChangeExtension($Trace, $null).TrimEnd('.')
# Insights strips backslashes from paths in its commands: forward slashes.
$Fwd = $Base -replace '\\', '/'
$Cmds = @()
foreach ($T in $Threads) {
	$Safe = ($T -replace '[^A-Za-z0-9]', '')
	$Cmds += "TimingInsights.ExportTimerStatistics `"$Fwd.$Safe.csv`" -threads=`"$T`""
}
$Rsp = "$Base.insights.rsp"
$Cmds | Set-Content -Encoding ASCII $Rsp
$P = Start-Process -FilePath $Insights -ArgumentList "-OpenTraceFile=`"$Trace`" -ExecOnAnalysisCompleteCmd=`"@=$Rsp`" -NoUI -AutoQuit -log" -PassThru -Wait -NoNewWindow
Get-ChildItem "$Base.*.csv" | ForEach-Object { Write-Host "$($_.Name)  $($_.Length) bytes" }
exit $P.ExitCode
