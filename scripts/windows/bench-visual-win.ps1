# The visual bench views (the same twelve as scripts/bench-visual.sh) on each quality tier of the packaged Windows
# game, with GPU time per budget slice. Writes Artifacts\visual-bench-<Label>.csv; with -Docs <dir> also copies each
# screenshot there as <view>-<tier>.png.
# Usage: scripts\windows\bench-visual-win.ps1 [-Seconds 12] [-Label pc] [-Tiers High,Ultra] [-ResX 3840 -ResY 2160]
#   -Only storm,helm-eye runs just those views (gate.ps1 picks them by scope; ONLY= on the Mac); -Extra adds arguments
#   to every view (BENCH_EXTRA=). One launch per view.
param(
	[int]$Seconds = 12,
	[string]$Label = 'pc',
	[string[]]$Tiers = @('High', 'Ultra'),
	[int]$ResX = 1920,
	[int]$ResY = 1080,
	[string]$Docs = '',
	[string]$Only = '',
	[string]$Extra = ''
)
. (Join-Path $PSScriptRoot 'env.ps1')
# From cmd (powershell -File) a list arrives as one string: High,Ultra
$Tiers = @($Tiers | ForEach-Object { $_ -split ',' } | Where-Object { $_ })

. (Join-Path $PSScriptRoot 'views.ps1')   # $Views: keep in step with VIEWS in scripts/bench-visual.sh
$Picked = @($Only -split ',' | Where-Object { $_ })

$Out = Join-Path $Artifacts "visual-bench-$Label.csv"
$Keys = 'total_ms', 'base_ms', 'lumen_ms', 'water_ms', 'clouds_fog_ms', 'niagara_ms', 'post_ms', 'other_ms'
'view,quality,avg_fps,p99_ms,gpu_ms,base_ms,lumen_ms,water_ms,clouds_fog_ms,niagara_ms,post_ms,other_ms,cloth_cpu_ms,water_cpu_ms' | Set-Content -Encoding ASCII $Out
foreach ($Name in @($Views.Keys | Where-Object { -not $Picked -or $Picked -contains $_ })) {
	foreach ($Q in $Tiers) {
		$Shot = "$Name-$($Q.ToLower())"
		$BenchJson = Join-Path $Artifacts 'bench.json'
		foreach ($Try in 1, 2) {
			Remove-Item -Force -ErrorAction SilentlyContinue $BenchJson
			& (Join-Path $PSScriptRoot 'bench-win.ps1') -Seconds $Seconds -ResX $ResX -ResY $ResY -Quality $Q -Shot $Shot -GameArgs "$($Views[$Name]) $Extra" -Demo | Out-Null
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
