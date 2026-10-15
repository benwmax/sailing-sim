# The whole Windows loop in one command: checks the PC, pulls the LFS content, brings in the MetaHuman crew if a zip
# is given or found, builds the editor, runs the tests, packages the game and runs a short Ultra benchmark.
# Usage (from the repo root; build-windows.bat at the root runs this with the same arguments):
#   scripts\windows\all.ps1 [-Config Development|Shipping] [-MetaHumansZip <path>] [-SkipTests] [-SkipPackage]
#                           [-SkipBench] [-Visual] [-BenchSeconds 20] [-ResX 1920 -ResY 1080]
#   -Visual also runs the twelve-view bench on High and Ultra (bench-visual-win.ps1; about half an hour).
# Each step stops the run on failure; logs are in Artifacts\.
param(
	[ValidateSet('Development', 'Shipping')][string]$Config = 'Development',
	[string]$MetaHumansZip = '',
	[switch]$SkipTests,
	[switch]$SkipPackage,
	[switch]$SkipBench,
	[switch]$Visual,
	[int]$BenchSeconds = 20,
	[int]$ResX = 1920,
	[int]$ResY = 1080
)
. (Join-Path $PSScriptRoot 'env.ps1')
$Started = Get-Date

function Step([string]$Text) { Write-Host ""; Write-Host "== $Text" -ForegroundColor Cyan }
function Fail([string]$Text) { Write-Host $Text -ForegroundColor Red; exit 1 }

Step 'Checking the PC'
$Git = Get-Command git -ErrorAction SilentlyContinue
if (-not $Git) { Fail 'git is not on the PATH (install Git for Windows).' }
$LfsOk = $false
try { $null = & git lfs version 2>&1; $LfsOk = ($LASTEXITCODE -eq 0) } catch { $LfsOk = $false }
if (-not $LfsOk) { Fail 'Git LFS is missing (install it from git-lfs.com, then run: git lfs install).' }
$VsWhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
if (Test-Path $VsWhere) {
	$Vs = & $VsWhere -latest -products * -requires Microsoft.VisualStudio.Workload.NativeGame -property displayName
	if ($Vs) { Write-Host "Visual Studio: $Vs" }
	else { Write-Host 'Visual Studio has no "Game development with C++" workload; the build will probably fail (see docs\windows\README.md).' -ForegroundColor Yellow }
} else {
	Write-Host 'Visual Studio Installer not found; the build needs Visual Studio with "Game development with C++".' -ForegroundColor Yellow
}
Write-Host "Unreal: $UERoot"
$Gpu = (Get-CimInstance Win32_VideoController -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name) -join ', '
if ($Gpu) { Write-Host "GPU: $Gpu" }
if ($RepoRoot.Length -gt 40) {
	Write-Host "The repo path is long ($RepoRoot). Unreal's intermediate paths can pass Windows' 260-character limit; D:\dev\sailing-sim is safer." -ForegroundColor Yellow
}

Step 'Pulling Git LFS content'
Push-Location $RepoRoot
try {
	& git lfs pull
	if ($LASTEXITCODE -ne 0) { Fail 'git lfs pull failed.' }
} finally { Pop-Location }
# A map that is still an LFS pointer means the content never came down: the editor would load an empty level.
$Map = Join-Path $RepoRoot 'Content\Maps\Lake.umap'
$Stream = [System.IO.File]::OpenRead($Map)
try { $Bytes = New-Object byte[] 24; $Read = $Stream.Read($Bytes, 0, 24) } finally { $Stream.Dispose() }
$Head = [System.Text.Encoding]::ASCII.GetString($Bytes, 0, $Read)
if ($Head.StartsWith('version https://git-lfs')) { Fail "Content\Maps\Lake.umap is an LFS pointer, not the map. Run: git lfs install; git lfs pull" }

Step 'MetaHuman crew'
$CrewDir = Join-Path $RepoRoot 'Content\Crew\MetaHumans'
if (-not $MetaHumansZip) {
	$Candidates = @((Join-Path $RepoRoot 'MetaHumans-for-PC.zip'), (Join-Path $env:USERPROFILE 'Downloads\MetaHumans-for-PC.zip'))
	$MetaHumansZip = $Candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if ($MetaHumansZip) {
	if (-not (Test-Path $MetaHumansZip)) { Fail "No zip at $MetaHumansZip" }
	Write-Host "Unpacking $MetaHumansZip into Content\Crew (replaces Content\Crew\MetaHumans)"
	Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $CrewDir
	Expand-Archive -Force -Path $MetaHumansZip -DestinationPath (Join-Path $RepoRoot 'Content\Crew')
}
if (Test-Path $CrewDir) {
	Write-Host 'MetaHuman crew present: Medium and up use it, with strand hair on High and Ultra.'
} else {
	Write-Host 'No MetaHuman crew (git-ignored; make it on the Mac with scripts/pack-metahumans.sh). The game falls back to the Blender crew.' -ForegroundColor Yellow
}

Step "Building the editor (SailingSimEditor Win64 Development)"
& (Join-Path $PSScriptRoot 'build.ps1')
if ($LASTEXITCODE -ne 0) { Fail 'Build failed; see Artifacts\build.log' }

if (-not $SkipTests) {
	Step 'Running the automation tests'
	& (Join-Path $PSScriptRoot 'test.ps1')
	if ($LASTEXITCODE -ne 0) { Fail 'Tests failed; see Artifacts\test.log and Artifacts\TestReport\index.json' }
}

if (-not $SkipPackage) {
	Step "Packaging the game ($Config)"
	& (Join-Path $PSScriptRoot 'package-win.ps1') -Config $Config
	if ($LASTEXITCODE -ne 0) { Fail 'Packaging failed; see Artifacts\package.log' }

	if (-not $SkipBench) {
		# The first launch on a GPU builds its DirectX 12 pipeline cache (stutters, maybe minutes): a short untimed run
		# warms it so the measured run is fair.
		Step 'Warming the GPU pipeline cache (first launch)'
		& (Join-Path $PSScriptRoot 'bench-win.ps1') -Seconds 5 -ResX $ResX -ResY $ResY -Quality Ultra -Shot warmup -StartupAllowance 900 | Out-Null
		Step "Benchmark: Ultra, $BenchSeconds s, ${ResX}x${ResY}, autopilot tacking"
		& (Join-Path $PSScriptRoot 'bench-win.ps1') -Seconds $BenchSeconds -ResX $ResX -ResY $ResY -Quality Ultra -Shot ultra -Demo
		if ($LASTEXITCODE -ne 0) { Fail 'Benchmark failed; see Artifacts\bench.log' }
		if ($Visual) {
			Step 'Visual bench: twelve views on High and Ultra'
			& (Join-Path $PSScriptRoot 'bench-visual-win.ps1') -Tiers High, Ultra -ResX $ResX -ResY $ResY
		}
	}
}

Step ("Done in {0:N0} min. Game: Packaged\Windows\SailingSim.exe   Logs and results: Artifacts\" -f ((Get-Date) - $Started).TotalMinutes)
exit 0
