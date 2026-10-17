# The soak: one long packaged run (2 hours by default) with the autopilot sailing and tacking, sampled every 30 s for the
# game's memory and the GPU's, then split into 30 s windows for fps and p99 from the frame trace. Writes
# Artifacts\soak\soak.csv (t_s, ram_mb, vram_mb, fps, p99_ms) and soak-summary.txt (10 minute windows), which
# scripts\budget-ledger.py reads (ram_growth_mb_per_hour, p99_drift_ms_per_hour, peak_ram_mb, peak_vram_mb).
#
#   scripts\windows\soak-win.ps1 [-Minutes 120] [-Quality Ultra] [-View beat15]
#
# VRAM is nvidia-smi's memory.used for the whole GPU (D3D12 graphics processes aren't listed per process), so leave the
# desktop quiet while it runs. RAM is the game process's private bytes.
param(
	[int]$Minutes = 120,
	[string]$Quality = 'Ultra',
	[string]$View = 'beat15',
	[int]$SampleSeconds = 30
)
. (Join-Path $PSScriptRoot 'env.ps1')
. (Join-Path $PSScriptRoot 'views.ps1')
if (-not $Views.Contains($View)) { throw "No view $View in views.ps1" }
$Out = Join-Path $Artifacts 'soak'
New-Item -ItemType Directory -Force $Out | Out-Null
$Shot = "soak-$View-$($Quality.ToLower())"
$Seconds = $Minutes * 60

$Job = Start-Job -ScriptBlock {
	param($Script, $Seconds, $Quality, $Shot, $GameArgs)
	& $Script -Seconds $Seconds -Quality $Quality -Shot $Shot -GameArgs "$GameArgs -SailingBenchTrace" -Demo -StartupAllowance 600
} -ArgumentList (Join-Path $PSScriptRoot 'bench-win.ps1'), $Seconds, $Quality, $Shot, $Views[$View]

# Samples from the moment the game's process appears (the trace's clock starts at its first frame, a few seconds later;
# the windows below line up on elapsed time, close enough at 30 s).
$Samples = New-Object System.Collections.Generic.List[object]
$Start = $null
while ($Job.State -eq 'Running') {
	$Game = Get-Process -Name 'SailingSim' -ErrorAction SilentlyContinue | Sort-Object PrivateMemorySize64 -Descending | Select-Object -First 1
	if ($Game) {
		if (-not $Start) { $Start = Get-Date }
		$Vram = (& nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>$null | Select-Object -First 1)
		$Samples.Add([pscustomobject]@{ t_s = [int]((Get-Date) - $Start).TotalSeconds; ram_mb = [math]::Round($Game.PrivateMemorySize64 / 1MB); vram_mb = "$Vram".Trim() })
	}
	Start-Sleep -Seconds $SampleSeconds
}
Receive-Job $Job | Out-File (Join-Path $Out 'bench-win.txt')
Remove-Job $Job

# Frame windows from the trace (elapsed s, frame ms).
$Trace = Get-SavedDirs | ForEach-Object { Join-Path $_ "Bench\$Shot.frames.csv" } | Where-Object { Test-Path $_ } | Select-Object -First 1
$Windows = @{}
if ($Trace) {
	Copy-Item -Force $Trace (Join-Path $Out "$Shot.frames.csv")
	foreach ($Line in [System.IO.File]::ReadLines($Trace)) {
		$Parts = $Line.Split(',')
		if ($Parts.Count -lt 2 -or -not ($Parts[0] -as [double])) { continue }
		$W = [int][math]::Floor([double]$Parts[0] / $SampleSeconds)
		if (-not $Windows.ContainsKey($W)) { $Windows[$W] = New-Object System.Collections.Generic.List[double] }
		$Windows[$W].Add([double]$Parts[1])
	}
}
$Rows = foreach ($S in $Samples) {
	$W = [int][math]::Floor($S.t_s / $SampleSeconds)
	$Fps = ''; $P99 = ''
	if ($Windows.ContainsKey($W) -and $Windows[$W].Count -gt 10) {
		$Ms = $Windows[$W] | Sort-Object
		$Fps = [math]::Round(1000.0 * $Ms.Count / ($Ms | Measure-Object -Sum).Sum, 1)
		$P99 = $Ms[[int][math]::Floor(0.99 * ($Ms.Count - 1))]
	}
	[pscustomobject]@{ t_s = $S.t_s; ram_mb = $S.ram_mb; vram_mb = $S.vram_mb; fps = $Fps; p99_ms = $P99 }
}
$Rows | Export-Csv -NoTypeInformation -Encoding ASCII (Join-Path $Out 'soak.csv')

# Ten minute windows for reading.
$Summary = @("soak: $View on $Quality, $Minutes min, $($Rows.Count) samples", 'window      fps   p99 ms   ram MB   vram MB')
foreach ($G in ($Rows | Group-Object { [int][math]::Floor($_.t_s / 600) } | Sort-Object { [int]$_.Name })) {
	$F = @($G.Group | Where-Object fps | ForEach-Object { [double]$_.fps })
	$P = @($G.Group | Where-Object p99_ms | ForEach-Object { [double]$_.p99_ms })
	$Summary += '{0,3}-{1,3} min {2,6} {3,8} {4,8} {5,9}' -f ([int]$G.Name * 10), ([int]$G.Name * 10 + 10),
		$(if ($F) { [math]::Round(($F | Measure-Object -Average).Average, 1) } else { '-' }),
		$(if ($P) { [math]::Round(($P | Measure-Object -Average).Average, 2) } else { '-' }),
		[math]::Round(($G.Group | Measure-Object ram_mb -Maximum).Maximum),
		$(($G.Group | Where-Object vram_mb | Measure-Object vram_mb -Maximum).Maximum)
}
$Summary | Set-Content -Encoding ASCII (Join-Path $Out 'soak-summary.txt')
$Summary | ForEach-Object { Write-Host $_ }
