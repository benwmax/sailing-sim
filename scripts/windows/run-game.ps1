# Runs the game uncooked from the editor binary (no packaging), for quick visual checks. Windows twin of
# scripts/run-game.sh: writes Saved\Bench\<shot>.png and bench.json; frame rates here are not representative.
# Usage: scripts\windows\run-game.ps1 -Seconds 10 -GameArgs "-SailingWeather=Thunderstorm -SailingShot=storm" [-ResX 1440 -ResY 1080]
#   -Capture <preset> -Shot <name> also passes -SailingCapture/-SailingShot; -NoDemo leaves the autopilot off.
param(
	[int]$Seconds = 10,
	[string]$GameArgs = '',
	[int]$ResX = 1440,
	[int]$ResY = 1080,
	[string]$Shot = '',
	[switch]$NoDemo
)
. (Join-Path $PSScriptRoot 'env.ps1')
$Editor = Join-Path $UERoot 'Engine\Binaries\Win64\UnrealEditor.exe'
$Bench = Join-Path $RepoRoot 'Saved\Bench'
Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $Bench 'bench.json')
$ArgLine = "`"$Project`" -game -windowed -ResX=$ResX -ResY=$ResY -SailingBench=$Seconds -nosplash"
if (-not $NoDemo) { $ArgLine += ' -SailingDemo' }
if ($Shot) { $ArgLine += " -SailingShot=$Shot" }
if ($GameArgs) { $ArgLine += " $GameArgs" }
$P = Start-Process -FilePath $Editor -ArgumentList $ArgLine -PassThru
$Deadline = (Get-Date).AddSeconds($Seconds + 300)
while (-not $P.HasExited -and (Get-Date) -lt $Deadline) { Start-Sleep -Seconds 1 }
if (-not $P.HasExited) {
	Write-Host 'Timed out (or hung); stopping the game' -ForegroundColor Yellow
	Stop-Process -Id $P.Id -Force -ErrorAction SilentlyContinue
}
$Json = Join-Path $Bench 'bench.json'
if (Test-Path $Json) { Get-Content -Raw $Json } else { Write-Host 'No bench.json; see Saved\Logs\SailingSim.log' -ForegroundColor Red; exit 1 }
if ($Shot -and (Test-Path (Join-Path $Bench "$Shot.png"))) { Write-Host "Screenshot: $(Join-Path $Bench "$Shot.png")" }
exit 0
