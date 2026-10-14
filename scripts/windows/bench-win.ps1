# Runs the packaged Windows game for a fixed time, prints the measured frame rate and copies the screenshot it takes
# into Artifacts\. Windows twin of scripts/bench-mac.sh (same game arguments, same bench.json).
# Usage: scripts\windows\bench-win.ps1 [-Seconds 20] [-ResX 1920] [-ResY 1080] [-Quality Ultra] [-Shot screenshot]
#                                      [-GameArgs "-SailingWeather=Thunderstorm -SailingHour=16"] [-Demo] [-Record 15]
#   -Quality: Low, Medium, High or Ultra (default: the game's setting, Ultra on Windows).
#   -Demo lets the autopilot sail and tack (-SailingDemo); -Record <s> also saves frames (Saved\Bench\rec).
# Needs a logged-in desktop that stays awake: it opens a window. Leave it in front; hidden windows run slower.
param(
	[int]$Seconds = 20,
	[int]$ResX = 1920,
	[int]$ResY = 1080,
	[string]$Quality = '',
	[string]$Shot = 'screenshot',
	[string]$GameArgs = '',
	[switch]$Demo,
	[int]$Record = 0,
	[int]$StartupAllowance = 180
)
. (Join-Path $PSScriptRoot 'env.ps1')

$Game = Join-Path $Packaged 'Windows\SailingSim.exe'
if (-not (Test-Path $Game)) { throw "No packaged game at $Game; run scripts\windows\package-win.ps1 first" }

$SavedDirs = Get-SavedDirs
foreach ($D in $SavedDirs) {
	$B = Join-Path $D 'Bench'
	Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $D 'Logs\SailingSim.log'), (Join-Path $B 'bench.json'),
		(Join-Path $B "$Shot.png"), (Join-Path $B "$Shot.camera.json"), (Join-Path $B "$Shot.telemetry.csv")
	Remove-Item -Recurse -Force -ErrorAction SilentlyContinue (Join-Path $B 'rec')
}

$ArgLine = "-SailingBench=$Seconds -windowed -ResX=$ResX -ResY=$ResY -SailingShot=$Shot"
if ($Quality) { $ArgLine += " -SailingQuality=$Quality" }
if ($Demo) { $ArgLine += ' -SailingDemo' }
if ($Record -gt 0) { $ArgLine += " -SailingRecord=$Record" }
if ($GameArgs) { $ArgLine += " $GameArgs" }
Write-Host "SailingSim.exe $ArgLine"

$P = Start-Process -FilePath $Game -ArgumentList $ArgLine -PassThru
# Warm-up + measurement + a generous startup allowance (more on the first launch: -StartupAllowance 900).
$Deadline = (Get-Date).AddSeconds($Seconds + $Record + $StartupAllowance)
while (-not $P.HasExited -and (Get-Date) -lt $Deadline) { Start-Sleep -Seconds 1 }
if (-not $P.HasExited) {
	Write-Host "Game did not finish in time; stopping it (is the desktop locked or asleep?)" -ForegroundColor Yellow
	Get-Process -Name 'SailingSim*' -ErrorAction SilentlyContinue | Stop-Process -Force
}

$Saved = $SavedDirs | Where-Object { Test-Path (Join-Path $_ 'Bench\bench.json') } | Select-Object -First 1
foreach ($D in $SavedDirs) {
	$L = Join-Path $D 'Logs\SailingSim.log'
	if (Test-Path $L) { Copy-Item -Force $L (Join-Path $Artifacts 'bench.log') }
}
if (-not $Saved) {
	Write-Host "No bench result; see Artifacts\bench.log" -ForegroundColor Red
	exit 1
}
$BenchDir = Join-Path $Saved 'Bench'
Copy-Item -Force (Join-Path $BenchDir 'bench.json') (Join-Path $Artifacts 'bench.json')
foreach ($Ext in 'png', 'camera.json', 'telemetry.csv') {
	$F = Join-Path $BenchDir "$Shot.$Ext"
	if (Test-Path $F) { Copy-Item -Force $F (Join-Path $Artifacts "$Shot.$Ext") }
}
$Json = Get-Content -Raw (Join-Path $Artifacts 'bench.json')
Write-Host "Bench: $Json"
Write-Host "Screenshot: $(Join-Path $Artifacts "$Shot.png")"
$Bench = $Json | ConvertFrom-Json
if ($Bench.gpu) {
	$G = $Bench.gpu
	Write-Host ("GPU ms: total {0}  base {1}  lumen {2}  water {3}  clouds+fog {4}  niagara {5}  post {6}  other {7}" -f
		$G.total_ms, $G.base_ms, $G.lumen_ms, $G.water_ms, $G.clouds_fog_ms, $G.niagara_ms, $G.post_ms, $G.other_ms)
}
Write-Host ("{0} fps average, p99 {1} ms, {2} on {3} at {4}" -f $Bench.avg_fps, $Bench.p99_ms, $Bench.quality, $Bench.rhi, $Bench.resolution)
if (Test-Path (Join-Path $BenchDir 'rec')) { Write-Host "Recorded frames: $(Join-Path $BenchDir 'rec')" }
exit 0
