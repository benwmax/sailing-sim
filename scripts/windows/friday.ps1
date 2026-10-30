# The Friday tester build (slice issue #406): one command from main to a zip for Bean and the testers.
# Usage: scripts\windows\friday.ps1 [-Commit <sha or ref>] [-NoCheckout] [-BenchSeconds 30]
#   Checks out origin/main (fetched) or -Commit, detached; -NoCheckout builds whatever is checked out (a dry run of a
#   branch). Refuses a tree with tracked changes.
#   Then: build.ps1, a full-cook Shipping package into Packaged\Shipping-<commit> (never over one that exists), with the
#   version line on the title screen (Content\BuildStamp\version.txt, removed afterwards); the smoke checks by launch args
#   and UI script only (no synthetic input): the game reaches Title > Gallery and renders its thumbnails, and two Ultra
#   Lake benches (the second reported: the first after a cook runs slow); the zip Packaged\SailingSim-<commit>-Win64.zip
#   (Windows' own tar.exe: zip64, the .ucas is over 2 GB) with TESTER-GUIDE.md in it; Packaged\Shipping-<commit>\BUILD.md
#   (commit, date, fps, the checks, the crash logs' place, what merged since the last Friday build).
#   Result line in Artifacts\friday-<commit>.txt. Bean does the gamepad and settings checks by hand.
param(
	[string]$Commit = '',
	[switch]$NoCheckout,
	[int]$BenchSeconds = 30
)
. (Join-Path $PSScriptRoot 'env.ps1')
$Start = Get-Date
Push-Location $RepoRoot
try {
	function Step([string]$Text) { Write-Host ("[{0:HH:mm:ss}] {1}" -f (Get-Date), $Text) -ForegroundColor Cyan }

	# 1. The commit.
	if (git status --porcelain --untracked-files=no) { throw 'Tracked changes in the tree: commit or set them aside first' }
	if (-not $NoCheckout) {
		$Ref = if ($Commit) { $Commit } else { 'origin/main' }
		Step "Checking out $Ref"
		git fetch -q origin main
		if ($LASTEXITCODE -ne 0) { throw 'git fetch failed' }
		git checkout -q --detach $Ref
		if ($LASTEXITCODE -ne 0) { throw "git checkout $Ref failed" }
	}
	$Sha = (git rev-parse --short=8 HEAD).Trim()
	$Subject = (git log -1 --format=%s HEAD).Trim()
	$Into = "Shipping-$Sha"
	$Folder = Join-Path $Packaged $Into
	$Zip = Join-Path $Packaged "SailingSim-$Sha-Win64.zip"
	if (Test-Path $Folder) { throw "$Folder exists: this commit already has a Friday build" }
	if (Test-Path $Zip) { throw "$Zip exists" }
	Step "Friday build of $Sha ($Subject)"

	# 2. Build and package, the version line staged with it.
	Step 'Building the editor target'
	& (Join-Path $PSScriptRoot 'build.ps1')
	if ($LASTEXITCODE -ne 0) { throw 'build.ps1 failed' }
	$StampDir = Join-Path $RepoRoot 'Content\BuildStamp'
	New-Item -ItemType Directory -Force $StampDir | Out-Null
	$Date = Get-Date -Format 'MMM d yyyy'
	# ASCII only: the game reads it without a byte order mark.
	[System.IO.File]::WriteAllText((Join-Path $StampDir 'version.txt'), "$Sha, $Date", [System.Text.Encoding]::ASCII)
	try {
		Step "Packaging Shipping into Packaged\$Into (full cook)"
		& (Join-Path $PSScriptRoot 'package-win.ps1') -Config Shipping -Full -Into $Into
		if ($LASTEXITCODE -ne 0) { throw 'package-win.ps1 failed' }
	} finally {
		Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $StampDir
	}
	$Exe = Join-Path $Folder 'Windows\SailingSim.exe'
	if (-not (Test-Path $Exe)) { throw "No $Exe after packaging" }

	# 3. Smoke checks: launch args and the UI script only.
	$Saved = Join-Path $env:LOCALAPPDATA 'SailingSim\Saved'
	function Run-Game([string]$GameArgs, [int]$TimeoutS) {
		$P = Start-Process -FilePath $Exe -ArgumentList "-SailingShippingSmoke $GameArgs -windowed -ResX=1920 -ResY=1080 -NoCrashReporter" -PassThru
		if (-not $P.WaitForExit($TimeoutS * 1000)) { throw "The game did not quit within $TimeoutS s ($GameArgs)" }
		return $P.ExitCode
	}
	# Title > Gallery: down to Quit, up past Credits, Enter; the gallery renders a thumbnail per mesh, then the script quits.
	Step 'Smoke: Title > Gallery'
	$Thumbs = Join-Path $Saved 'GalleryThumbs'
	Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $Thumbs
	$Walk = (@('Wait', 'Wait', 'Wait') + (1..20 | ForEach-Object { 'Down' }) + @('Up', 'Up', 'Enter') + (1..10 | ForEach-Object { 'Wait' }) + @('Quit')) -join ','
	$GalleryExit = Run-Game "-SailingUIScript=$Walk" 300
	$ThumbCount = if (Test-Path $Thumbs) { @(Get-ChildItem $Thumbs -Filter *.png).Count } else { 0 }
	$GalleryOk = $GalleryExit -eq 0 -and $ThumbCount -gt 100
	Write-Host "  exit $GalleryExit, $ThumbCount thumbnails: $(if ($GalleryOk) { 'ok' } else { 'FAILED' })"
	# Two Ultra benches on the lake; the second is the number (the first after a cook runs slow).
	$Json = Join-Path $Saved 'Bench\bench.json'
	$Benches = @()
	foreach ($Run in 1..2) {
		Step "Smoke: Ultra Lake bench $Run of 2"
		Remove-Item -Force -ErrorAction SilentlyContinue $Json
		$null = Run-Game "-SailingWorld=Lake -SailingLaunch=1 -SailingBench=$BenchSeconds -SailingShot=friday-$Sha" ($BenchSeconds + 240)
		if (-not (Test-Path $Json)) { throw "Bench $Run wrote no bench.json" }
		$Benches += Get-Content -Raw $Json | ConvertFrom-Json
		Write-Host ("  {0} fps, p99 {1} ms, GPU {2} ms, {3}" -f $Benches[-1].avg_fps, $Benches[-1].p99_ms, $Benches[-1].gpu_frame_ms, $Benches[-1].quality)
	}
	$B = $Benches[1]

	# 4. BUILD.md, and what merged since the last Friday build (the newest other BUILD.md's commit).
	$Previous = Get-ChildItem -Path $Packaged -Filter BUILD.md -Recurse -Depth 1 -ErrorAction SilentlyContinue |
		Where-Object { $_.DirectoryName -ne $Folder } | Sort-Object LastWriteTime -Descending | Select-Object -First 1
	$PrevSha = ''
	if ($Previous) { $PrevSha = ((Select-String -Path $Previous.FullName -Pattern '^- Commit: `([0-9a-f]+)`' | Select-Object -First 1).Matches.Groups[1].Value) }
	$Merged = if ($PrevSha) { @(git log --first-parent --format='- %s (%h)' "$PrevSha..HEAD") } else { @(git log --first-parent --format='- %s (%h)' -20 HEAD) }
	$Since = if ($PrevSha) { "since the last Friday build, ``$PrevSha``" } else { 'the last 20 on main (no earlier Friday build on this PC)' }
	$Md = @(
		"# SailingSim Friday build $Sha",
		'',
		"- Commit: ``$Sha`` ($Subject)",
		"- Built: $(Get-Date -Format 'yyyy-MM-dd HH:mm') on Bean's RTX 4090 PC, Windows Shipping, full cook",
		"- Zip: ``Packaged\SailingSim-$Sha-Win64.zip`` (unzip anywhere, run ``SailingSim.exe``; see TESTER-GUIDE.md inside)",
		"- The title screen's bottom corner reads: Build $Sha, $Date",
		'',
		'## Smoke checks (launch args and a UI script only; gamepad and settings by hand)',
		'',
		"- Title > Gallery: $(if ($GalleryOk) { 'opens' } else { 'FAILED' }) ($ThumbCount thumbnails rendered, game exit $GalleryExit)",
		("- Ultra, Lake, 1920x1080, {0} s: **{1} fps**, p99 {2} ms, GPU {3} ms, game thread {4} ms (second of two runs; the first gave {5} fps)" -f $BenchSeconds, $B.avg_fps, $B.p99_ms, $B.gpu_frame_ms, $B.game_ms, $Benches[0].avg_fps),
		'',
		'## Crash logs',
		'',
		'`%LOCALAPPDATA%\SailingSim\Saved\Logs` (the log) and `%LOCALAPPDATA%\SailingSim\Saved\Crashes` (a folder per crash). Zip and send both with a report.',
		'',
		"## Merged $Since",
		''
	) + $Merged
	Set-Content -Path (Join-Path $Folder 'BUILD.md') -Value $Md -Encoding UTF8

	# 5. The zip: the game folder, the tester guide and BUILD.md.
	Step "Zipping to $Zip"
	Copy-Item -Force (Join-Path $RepoRoot 'docs\windows\TESTER-GUIDE.md') (Join-Path $Folder 'Windows\TESTER-GUIDE.md')
	Copy-Item -Force (Join-Path $Folder 'BUILD.md') (Join-Path $Folder 'Windows\BUILD.md')
	$Tar = Join-Path $env:SystemRoot 'System32\tar.exe'
	& $Tar -a -c -f $Zip -C (Join-Path $Folder 'Windows') .
	if ($LASTEXITCODE -ne 0) { throw 'tar.exe failed to write the zip' }
	$ZipGb = (Get-Item $Zip).Length / 1GB

	$Result = "Friday build $Sha done in {0:N0} min: {1}, {2:N2} GB; gallery {3}; Ultra {4} fps (second run)" -f ((Get-Date) - $Start).TotalMinutes, $Zip, $ZipGb, $(if ($GalleryOk) { 'ok' } else { 'FAILED' }), $B.avg_fps
	Set-Content -Path (Join-Path $Artifacts "friday-$Sha.txt") -Value $Result
	Write-Host $Result -ForegroundColor Green
	if (-not $GalleryOk) { exit 1 }
} finally {
	Pop-Location
}
