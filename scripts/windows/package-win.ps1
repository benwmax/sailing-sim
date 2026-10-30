# Builds, cooks, stages and archives a standalone Windows game with RunUAT BuildCookRun. Windows twin of
# scripts/package-mac.sh (same steps: -build -cook -stage -pak -iostore -package -archive).
# Usage: scripts\windows\package-win.ps1 [-Config Development|Shipping] [-Full] [-Into <folder under Packaged>]
#   Output: Packaged\Windows\SailingSim.exe (or Packaged\<Into>\Windows\SailingSim.exe)     Log: Artifacts\package.log
#   -Into archives into a folder of its own (friday.ps1's Packaged\Shipping-<commit>); it refuses one that exists.
#   The cook is incremental (-cookincremental: the Zen store keeps the last cook, and only what changed and what depends
#   on it is cooked again); -Full cooks everything. Timings: docs/windows/README.md, "Build times". gate.ps1 skips the
#   whole package when nothing it's made from has changed.
# Never archive into Build\: that is Unreal's own platform folder.
param(
	[ValidateSet('Development', 'Shipping')][string]$Config = 'Development',
	[switch]$Full,
	[string]$Into = ''
)
. (Join-Path $PSScriptRoot 'env.ps1')

$Archive = if ($Into) { Join-Path $Packaged $Into } else { $Packaged }
if ($Into -and (Test-Path $Archive)) { throw "$Archive exists: package into a new folder, never over a build" }

$Cook = if ($Full) { '-cook' } else { '-cook -cookincremental' }
$ArgLine = "BuildCookRun -project=`"$Project`" -noP4 -utf8output -unattended -platform=Win64 -clientconfig=$Config " +
	"-build $Cook -stage -pak -iostore -package -archive -crashreporter -archivedirectory=`"$Archive`""
$Start = Get-Date
$Code = Invoke-Tool $RunUAT $ArgLine (Join-Path $Artifacts 'package.log')
if ($Code -eq 0) {
	Write-Host ("Packaged game ({0:N0} s, {1} cook):" -f ((Get-Date) - $Start).TotalSeconds, $(if ($Full) { 'full' } else { 'incremental' }))
	Get-ChildItem -Path (Join-Path $Archive 'Windows') -Filter 'SailingSim*.exe' -ErrorAction SilentlyContinue | ForEach-Object { Write-Host "  $($_.FullName)" }
} else {
	Write-Host "Packaging failed (exit $Code). See Artifacts\package.log" -ForegroundColor Red
}
exit $Code
