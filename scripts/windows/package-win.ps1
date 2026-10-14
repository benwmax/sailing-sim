# Builds, cooks, stages and archives a standalone Windows game with RunUAT BuildCookRun. Windows twin of
# scripts/package-mac.sh (same steps: -build -cook -stage -pak -iostore -package -archive).
# Usage: scripts\windows\package-win.ps1 [-Config Development|Shipping]
#   Output: Packaged\Windows\SailingSim.exe     Log: Artifacts\package.log
# Never archive into Build\: that is Unreal's own platform folder.
param([ValidateSet('Development', 'Shipping')][string]$Config = 'Development')
. (Join-Path $PSScriptRoot 'env.ps1')

$ArgLine = "BuildCookRun -project=`"$Project`" -noP4 -utf8output -unattended -platform=Win64 -clientconfig=$Config " +
	"-build -cook -stage -pak -iostore -package -archive -archivedirectory=`"$Packaged`""
$Code = Invoke-Tool $RunUAT $ArgLine (Join-Path $Artifacts 'package.log')
if ($Code -eq 0) {
	Write-Host "Packaged game:"
	Get-ChildItem -Path (Join-Path $Packaged 'Windows') -Filter 'SailingSim*.exe' -ErrorAction SilentlyContinue | ForEach-Object { Write-Host "  $($_.FullName)" }
} else {
	Write-Host "Packaging failed (exit $Code). See Artifacts\package.log" -ForegroundColor Red
}
exit $Code
