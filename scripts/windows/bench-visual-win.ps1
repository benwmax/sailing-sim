# The visual bench views (the same twelve as scripts/bench-visual.sh) on each quality tier of the packaged Windows
# game, with GPU time per budget slice. Writes Artifacts\visual-bench-<Label>.csv; with -Docs <dir> also copies each
# screenshot there as <view>-<tier>.png.
# Usage: scripts\windows\bench-visual-win.ps1 [-Seconds 12] [-Label pc] [-Tiers High,Ultra] [-ResX 3840 -ResY 2160]
param(
	[int]$Seconds = 12,
	[string]$Label = 'pc',
	[string[]]$Tiers = @('High', 'Ultra'),
	[int]$ResX = 1920,
	[int]$ResY = 1080,
	[string]$Docs = ''
)
. (Join-Path $PSScriptRoot 'env.ps1')
# From cmd (powershell -File) a list arrives as one string: High,Ultra
$Tiers = @($Tiers | ForEach-Object { $_ -split ',' } | Where-Object { $_ })

# Keep in step with VIEWS in scripts/bench-visual.sh.
$Views = [ordered]@{
	"beam8" = "-SailingWorld=Lake -SailingLaunch=1 -SailingWeather=AfternoonBreeze -SailingHour=12 -SailingWind=8 -SailingTWA=90 -SailingHoldTWA=90 -SailingCamYaw=200 -SailingCamPitch=-10"
	"beat15" = "-SailingWorld=Lake -SailingLaunch=1 -SailingWeather=AfternoonBreeze -SailingHour=16 -SailingWind=15 -SailingTWA=45"
	"storm" = "-SailingWorld=Lake -SailingLaunch=1 -SailingWeather=Thunderstorm -SailingHour=16 -SailingWeatherTime=200 -SailingTWA=100 -SailingHoldTWA=100 -SailingCamYaw=200 -SailingCamPitch=-8"
	"marina" = "-SailingWorld=Lake -SailingLaunch=0 -SailingWeather=AfternoonBreeze -SailingHour=10 -SailingWind=6 -SailingCamYaw=150 -SailingCamPitch=-12 -SailingCamDist=40"
	"coast-day" = "-SailingWorld=1 -SailingLaunch=1 -SailingWeather=AfternoonBreeze -SailingWind=12 -SailingTWA=60 -SailingHoldTWA=60 -SailingHour=11 -SailingCamYaw=250 -SailingCamPitch=-10"
	"coast-night" = "-SailingWorld=1 -SailingLaunch=1 -SailingWeather=AfternoonBreeze -SailingWind=12 -SailingTWA=60 -SailingHoldTWA=60 -SailingHour=21 -SailingCamYaw=150 -SailingCamPitch=-6 -SailingCamDist=14"
	"gulf-sea" = "-SailingWorld=Gulf -SailingLaunch=2 -SailingWeather=AfternoonBreeze -SailingWind=12 -SailingTWA=60 -SailingHoldTWA=60 -SailingHour=11 -SailingCamYaw=200 -SailingCamPitch=-5 -SailingCamDist=22"
	"helm-eye" = "-SailingWorld=Lake -SailingLaunch=1 -SailingCapture=HelmEye -SailingWeather=AfternoonBreeze -SailingWind=12 -SailingHour=15 -SailingTWA=45 -SailingHoldTWA=45"
	"slip" = "-SailingWorld=Lake -SailingDrill=LeavetheDock -SailingWeather=AfternoonBreeze -SailingHour=10 -SailingWind=6 -SailingCamYaw=160 -SailingCamPitch=-14 -SailingCamDist=26"
	"bridge" = "-SailingWorld=Lake -SailingStartAt=7060,880,183 -SailingKeepStart -SailingWeather=AfternoonBreeze -SailingHour=11 -SailingWind=8 -SailingCamYaw=180 -SailingCamPitch=-4 -SailingCamDist=20"
	"crew" = "-SailingWorld=Lake -SailingLaunch=1 -SailingWeather=AfternoonBreeze -SailingHour=15 -SailingWind=10 -SailingTWA=60 -SailingHoldTWA=60 -SailingCamYaw=250 -SailingCamPitch=-6 -SailingCamDist=2.6 -SailingCamTarget=-1.6,0.8,0.9"
	"marina-night" = "-SailingWorld=Lake -SailingDrill=LeavetheDock -SailingWeather=AfternoonBreeze -SailingHour=21.5 -SailingWind=4 -SailingCamYaw=200 -SailingCamPitch=-10 -SailingCamDist=40"
}

$Out = Join-Path $Artifacts "visual-bench-$Label.csv"
$Keys = 'total_ms', 'base_ms', 'lumen_ms', 'water_ms', 'clouds_fog_ms', 'niagara_ms', 'post_ms', 'other_ms'
'view,quality,avg_fps,p99_ms,gpu_ms,base_ms,lumen_ms,water_ms,clouds_fog_ms,niagara_ms,post_ms,other_ms,cloth_cpu_ms,water_cpu_ms' | Set-Content -Encoding ASCII $Out
foreach ($Name in $Views.Keys) {
	foreach ($Q in $Tiers) {
		$Shot = "$Name-$($Q.ToLower())"
		$BenchJson = Join-Path $Artifacts 'bench.json'
		foreach ($Try in 1, 2) {
			Remove-Item -Force -ErrorAction SilentlyContinue $BenchJson
			& (Join-Path $PSScriptRoot 'bench-win.ps1') -Seconds $Seconds -ResX $ResX -ResY $ResY -Quality $Q -Shot $Shot -GameArgs $Views[$Name] -Demo | Out-Null
			if (Test-Path $BenchJson) { break }
		}
		if (Test-Path $BenchJson) {
			$B = Get-Content -Raw $BenchJson | ConvertFrom-Json
			$Gpu = ($Keys | ForEach-Object { if ($B.gpu) { $B.gpu.$_ } else { '' } }) -join ','
			"$Name,$Q,$($B.avg_fps),$($B.p99_ms),$Gpu,$($B.cloth_cpu_ms),$($B.water_cpu_ms)" | Add-Content -Encoding ASCII $Out
			Write-Host ("{0,-14} {1,-6} {2,6} fps  p99 {3} ms" -f $Name, $Q, $B.avg_fps, $B.p99_ms)
		} else {
			"$Name,$Q,error,,,,,,,,,,," | Add-Content -Encoding ASCII $Out
			Write-Host ("{0,-14} {1,-6} error (see Artifacts\bench.log)" -f $Name, $Q) -ForegroundColor Red
		}
		$Png = Join-Path $Artifacts "$Shot.png"
		if ($Docs -and (Test-Path $Png)) {
			New-Item -ItemType Directory -Force -Path $Docs | Out-Null
			Copy-Item -Force $Png (Join-Path $Docs "$Shot.png")
		}
	}
}
Write-Host "Results: $Out"
