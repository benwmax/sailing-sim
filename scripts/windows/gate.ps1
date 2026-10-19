# Bench-fast on the PC (the Windows twin of scripts/gate.sh; docs/bench-fast): the gate for a change, scoped to what it
# can affect. Same scopes, sentinel views, hashes and heavy-test list as the Mac's.
#   scripts\windows\gate.ps1 -Scope clouds|water|boats|crew|world|ui|night|all [-Seconds 12] [-Label name] [-Baseline csv]
#                            [-Tests <filter> | -NoTests] [-Tiers High,Ultra] [-Force] [-Merge <ref>,<ref>]
# -Merge gates several PRs as one batch: a local branch gate-<n> from origin/main with each ref merged in (fetched first; a
# conflict stops the gate), so one build, one test run, one package and one bench cover them all.
# Builds, tests and packages only when their inputs changed since the last pass (hashes in Artifacts\gate\, by content:
# Get-InputsHash in env.ps1 is gate.sh's inputs_hash), then benches the scope's views on the PC's tiers (High and Ultra;
# bench-visual-win.ps1, one launch per view) and checks the Mac's gates where those tiers were measured (Medium 60, High
# 45). `all` is the full sweep (every view; add -Tiers Low,Medium,High,Ultra for every tier). -Baseline compares each
# view with an earlier visual-bench CSV.
param(
	[ValidateSet('clouds', 'sky', 'water', 'boats', 'crew', 'world', 'night', 'ui', 'all')][string]$Scope = 'all',
	[int]$Seconds = 12,
	[string]$Label = '',
	[string]$Baseline = '',
	[string]$Tests = 'SailingSim',
	[switch]$NoTests,
	[string[]]$Tiers = @('High', 'Ultra'),
	[switch]$Force,
	[string[]]$Merge = @()
)
. (Join-Path $PSScriptRoot 'env.ps1')
$ErrorActionPreference = 'Continue'   # git and the tools report on stderr; their exit codes decide
$Tiers = @($Tiers | ForEach-Object { $_ -split ',' } | Where-Object { $_ })
$Merge = @($Merge | ForEach-Object { $_ -split ',' } | Where-Object { $_ })
if ($NoTests) { $Tests = '' }

# The three tightest High views (about 1 fps over 45 after W2) run in every scope.
$Sentinels = 'helm-eye,slip,coast-day'
$Views = switch ($Scope) {
	{ $_ -in 'clouds', 'sky' } { 'beam8,beat15,storm,gulf-sea,bridge' }
	'water' { 'beam8,beat15,storm,marina,gulf-sea,bridge' }
	'boats' { 'beam8,beat15,marina,crew' }
	'crew' { 'beat15,crew' }
	'world' { 'marina,bridge,coast-night,marina-night,marseille-port,far-coast,far-coast-night' }
	'night' { 'coast-night,marina-night' }
	'ui' { 'beam8' }
	'all' { '' }
}
if ($Views) { $Views = "$Views,$Sentinels" }
if (-not $Label) { $Label = "gate-$Scope" }
$State = Join-Path $Artifacts 'gate'
New-Item -ItemType Directory -Force -Path $State | Out-Null
Set-Location $RepoRoot

if ($Merge) {
	if (git status --porcelain --untracked-files=no) { Write-Host 'Uncommitted changes: commit or stash before -Merge' -ForegroundColor Red; exit 1 }
	git fetch -q origin main @Merge
	$Branch = "gate-$(Get-Date -Format 'MMdd-HHmm')"
	git checkout -q -B $Branch origin/main
	foreach ($Ref in $Merge) {
		git merge -q --no-edit "origin/$Ref" 2>$null
		if ($LASTEXITCODE -ne 0) { git merge --abort 2>$null; git merge -q --no-edit $Ref }
		if ($LASTEXITCODE -ne 0) { Write-Host "Merging $Ref into $Branch conflicts: resolve it, commit, then run the gate without -Merge" -ForegroundColor Red; exit 1 }
	}
	Write-Host "[gate] ${Branch}: origin/main + $($Merge -join ' ')"
}

$CodeHash = Get-InputsHash Source, SailingSim.uproject, Config, Plugins
$PackageHash = Get-InputsHash Source, SailingSim.uproject, Config, Plugins, Content
$T0 = Get-Date
function Step([string]$What) { Write-Host ("[gate {0:N0} s] {1}" -f ((Get-Date) - $T0).TotalSeconds, $What) }
function Stamp([string]$Name) { $P = Join-Path $State $Name; if (Test-Path $P) { (Get-Content -Raw $P).Trim() } else { '' } }
function Child([string]$Script, [string[]]$Arguments) {
	# Each step in its own PowerShell: they end with exit, and their console output goes to a file, not this one.
	$Out = Join-Path $State "$([System.IO.Path]::GetFileNameWithoutExtension($Script)).out"
	& pwsh -NoProfile -File (Join-Path $PSScriptRoot $Script) @Arguments *> $Out
	return $LASTEXITCODE
}

if ($Force -or (Stamp 'build.hash') -ne $CodeHash) {
	Step 'build'
	if ((Child 'build.ps1') -ne 0) { Write-Host 'Build failed: Artifacts\build.log' -ForegroundColor Red; exit 1 }
	Set-Content (Join-Path $State 'build.hash') $CodeHash
} else { Step 'build: nothing changed since the last build' }

# The heavy tests (scripts/gate-heavy-tests.txt) read only the physics, the tests and the terrain bake (and the few game
# files the test sources include): when none of those changed since they last passed, the rest run alone.
$HeavyHash = Get-InputsHash Source/SailingPhysics, Source/SailingSimTests, Content/TerrainData, Source/SailingSim/Public/LakeData.h,
	Source/SailingSim/Private/LakeData.cpp, Source/SailingSim/Public/Chart.h, Source/SailingSim/Private/Chart.cpp,
	Source/SailingSim/Public/Navigation.h, Source/SailingSim/Private/Navigation.cpp, Source/SailingSim/Public/ReferenceCapture.h,
	Source/SailingSim/Private/ReferenceCapture.cpp
function Invoke-Tests([string]$Filter) {
	if ((Child 'test.ps1' @('-Filter', $Filter)) -ne 0) {
		Select-String (Join-Path $State 'test.out') -Pattern '^Fail|!' | ForEach-Object { Write-Host $_.Line -ForegroundColor Red }
		Write-Host 'Tests failed: Artifacts\gate\test.out' -ForegroundColor Red; exit 1
	}
	Get-Content (Join-Path $State 'test.out') | Where-Object { $_ -match 'passed' } | Select-Object -Last 1
}
if ($Tests) {
	$AllList = Join-Path $State 'tests-all.txt'
	# Content is in the tests' inputs too (maps, materials, terrain data).
	if (-not $Force -and (Stamp 'tests.hash') -eq "$PackageHash $Tests") {
		Step 'tests: passed on these inputs already'
	} elseif (-not $Force -and $Tests -eq 'SailingSim' -and (Test-Path $AllList) -and (Stamp 'heavy.hash') -eq $HeavyHash) {
		$Heavy = @(Get-Content (Join-Path $RepoRoot 'scripts\gate-heavy-tests.txt') | ForEach-Object { $_.Trim() } | Where-Object { $_ -and -not $_.StartsWith('#') })
		$Light = @(Get-Content $AllList | Where-Object { $N = $_.Trim(); $N -and -not ($Heavy | Where-Object { $N.StartsWith($_) }) })
		Step "tests: the heavy set passed on these physics inputs; $($Light.Count) others"
		# (Windows caps a command line at 32K characters: a longer list runs as the whole suite.)
		Invoke-Tests $(if (($Light -join '+').Length -lt 30000) { $Light -join '+' } else { $Tests })
		# New tests (not in the last full run's list) are picked up by the next full run.
		Set-Content (Join-Path $State 'tests.hash') "$PackageHash $Tests"
	} else {
		Step "tests ($Tests)"
		Invoke-Tests $Tests
		Set-Content (Join-Path $State 'tests.hash') "$PackageHash $Tests"
		if ($Tests -eq 'SailingSim') {
			Set-Content (Join-Path $State 'heavy.hash') $HeavyHash
			$Report = Get-Content -Raw (Join-Path $Artifacts 'TestReport\index.json') | ConvertFrom-Json
			$Report.tests | ForEach-Object { $_.fullTestPath } | Set-Content $AllList
		}
	}
}

if ($Force -or -not (Test-Path (Join-Path $Packaged 'Windows\SailingSim.exe')) -or (Stamp 'package.hash') -ne $PackageHash) {
	Step 'package'
	if ((Child 'package-win.ps1') -ne 0) { Write-Host 'Package failed: Artifacts\package.log' -ForegroundColor Red; exit 1 }
	Set-Content (Join-Path $State 'package.hash') $PackageHash
} else { Step 'package: the packaged game is already this tree' }

Step "bench $(if ($Views) { $Views } else { 'every view' }) on $($Tiers -join ' ')"
$BenchArgs = @('-Seconds', $Seconds, '-Label', $Label, '-Tiers', ($Tiers -join ','))
if ($Views) { $BenchArgs += @('-Only', $Views) }
$null = Child 'bench-visual-win.ps1' $BenchArgs
Step 'done'

$Rows = Import-Csv (Join-Path $Artifacts "visual-bench-$Label.csv")
$Base = @{}
if ($Baseline) { Import-Csv $Baseline | ForEach-Object { $Base["$($_.view)|$($_.quality)"] = $_ } }
$Gate = @{ 'Medium' = 60.0; 'High' = 45.0 }
$Fail = 0
Write-Host (("{0,-14} {1,-7} {2,6} {3,7} {4,7}" -f 'view', 'tier', 'fps', 'p99 ms', 'gpu ms') + $(if ($Baseline) { " {0,9} {1,6}" -f 'base fps', 'delta' } else { '' }) + '  gate')
foreach ($R in $Rows) {
	$Fps = 0.0
	if (-not [double]::TryParse($R.avg_fps, [ref]$Fps)) { Write-Host ("{0,-14} {1,-7}  error" -f $R.view, $R.quality); $Fail++; continue }
	$G = $Gate[$R.quality]
	$Ok = (-not $G) -or $Fps -ge $G
	if (-not $Ok) { $Fail++ }
	$Line = "{0,-14} {1,-7} {2,6:N1} {3,7} {4,7}" -f $R.view, $R.quality, $Fps, $R.p99_ms, $R.gpu_ms
	if ($Baseline) {
		$B = $Base["$($R.view)|$($R.quality)"]; $BF = 0.0
		$Line += if ($B -and [double]::TryParse($B.avg_fps, [ref]$BF)) { " {0,9} {1,6:+0.0;-0.0}" -f $B.avg_fps, ($Fps - $BF) } else { ' ' * 17 }
	}
	Write-Host ($Line + $(if ($Ok) { '  ok' } else { "  UNDER $G" }))
}
Write-Host "gate: $(if ($Fail -eq 0) { 'pass' } else { "$Fail view(s) under the gate or lost" })"
exit $(if ($Fail -eq 0) { 0 } else { 1 })
