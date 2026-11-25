# Nov 24: one film-mode recording on Packaged\Windows-6630fe1e. Writes the shot file to the package's Saved\reel\<shot>.json,
# launches with the COMMON args + -SailingCapture=Path, waits, moves Saved\Bench\rec to D:\dev\reel\rehearsal-6630fe1e\<Name>,
# copies the log, camera.json, telemetry. Bean's Saved held aside. Ends only its own processes, by PID.
param([Parameter(Mandatory)][string]$Name, [Parameter(Mandatory)][string]$ShotJson, [string]$ShotFile, [double]$Record = 2, [string]$Extra = '', [int]$Timeout = 600, [double]$Warmup = 10, [string]$PkgName = 'Windows-6630fe1e', [string]$ReelDir = 'rehearsal-6630fe1e', [int]$ResX = 3840, [int]$ResY = 2160, [double]$Bench = 3, [switch]$Hud, [switch]$NoPath, [string]$Interval = '0.0166667', [string]$SeedProfile = '')
$Main = 'D:\dev\ss-fix'; $Pkg = "$Main\Packaged\$PkgName"; $Saved = "$Pkg\SailingSim\Saved"
$Dst = "D:\dev\reel\$ReelDir\$Name"; if (Test-Path $Dst) { throw "$Dst exists" }
New-Item -ItemType Directory -Force $Dst, "$Saved\reel" | Out-Null
if (-not $ShotFile) { $ShotFile = $Name }
Set-Content "$Saved\reel\$ShotFile.json" $ShotJson -NoNewline
$common = "-benchmark -fps=60 -SailingQuality=Ultra -ResX=$ResX -ResY=$ResY -ForceRes -windowed -SailingFilm -SailingCinematic=1$(if ($Hud) { '' } else { ' -SailingNoHud' }) -SailingNoGpuSlices -SailingShowCrew=0 -SailingTraffic=0 -SailingSeed=7 -SailingBenchWarmup=$Warmup -SailingRecordInterval=$Interval"
$a = "$common -SailingBench=$Bench -SailingRecord=$Record$(if ($NoPath) { '' } else { " -SailingCapture=Path -SailingShotFile=reel/$ShotFile.json" }) -SailingShot=$Name $Extra"
$Local = Join-Path $env:LOCALAPPDATA 'SailingSim'; $SavedDir = Join-Path $Local 'Saved'; $HoldDir = Join-Path $Local 'Saved.bench-hold'; $held = $false
try {
	if (@(Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'SailingSim*' -or $_.Name -like 'UnrealEditor*' }).Count) { throw 'a game or editor is running' }
	if (Test-Path $HoldDir) { throw "$HoldDir exists" }
	if (Test-Path $SavedDir) { Rename-Item $SavedDir 'Saved.bench-hold' -ErrorAction Stop; $held = $true }
	if ($SeedProfile) { New-Item -ItemType Directory -Force "$SavedDir\SaveGames" | Out-Null; Copy-Item $SeedProfile "$SavedDir\SaveGames\profile.json" -Force }   # a throwaway test profile, never Bean's
	if (Test-Path "$Saved\Bench\rec") { Move-Item "$Saved\Bench\rec" "$Dst\stale-rec" }
	$t1 = Get-Date; $P = Start-Process -FilePath "$Pkg\SailingSim.exe" -ArgumentList $a -PassThru
	while (((Get-Date) - $t1).TotalSeconds -lt $Timeout) { Start-Sleep 3; if (-not @(Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'SailingSim*' -and $_.ExecutablePath -like "$Pkg\*" }).Count) { break } }
	$left = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'SailingSim*' -and $_.ExecutablePath -like "$Pkg\*" })
	$left | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
	$secs = [int]((Get-Date) - $t1).TotalSeconds
	if (Test-Path "$Saved\Bench\rec") { Move-Item "$Saved\Bench\rec" "$Dst\rec" }
	foreach ($f in @(Get-ChildItem "$Saved\Bench" -File | Where-Object { $_.LastWriteTime -gt $t1 })) { Copy-Item $f.FullName $Dst -Force }
	$glog = Get-ChildItem "$Saved\Logs" -Filter '*.log' | Where-Object { $_.LastWriteTime -gt $t1 } | Sort-Object LastWriteTime | Select-Object -Last 1
	if ($glog) { Copy-Item $glog.FullName "$Dst\game.log" -Force }
	Set-Content "$Dst\args.txt" "Packaged\$PkgName\SailingSim.exe $a"
	Copy-Item "$Saved\reel\$ShotFile.json" $Dst
	$n = @(Get-ChildItem "$Dst\rec" -Filter 'frame_*.png' -ErrorAction SilentlyContinue).Count
	$recline = if ($glog) { (Select-String "$Dst\game.log" -Pattern 'SailingRecord:|ShotFile|shot file|Capture' | Select-Object -Last 4 | ForEach-Object { $_.Line.Trim() }) -join ' / ' }
	"$Name`: $n frames, $secs s$(if ($left.Count) { ', stopped my leftover ' + ($left.ProcessId -join ',') }); $recline"
} finally {
	if ($held) {
		Start-Sleep 2
		if (Test-Path $SavedDir) { Rename-Item $SavedDir ('Saved.rec-' + (Get-Date -Format HHmmss)) }
		for ($i = 0; $i -lt 20 -and -not (Test-Path $SavedDir); $i++) { try { Rename-Item $HoldDir 'Saved' -ErrorAction Stop } catch { Start-Sleep 5 } }
		"profile $((Get-FileHash (Join-Path $SavedDir 'SaveGames\profile.json') -ErrorAction SilentlyContinue).Hash.Substring(0,8))"
	}
}
