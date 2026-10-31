# Records the sim reel's showcase loops on the PC (docs/sim-reel/PC-RUNBOOK.md): Movie Render Queue renders the game
# from the editor binary, then the loop is composed and encoded. Windows twin of scripts/capture-reel.sh; the footage is
# made here (the Mac's renders are smoke tests). Needs scripts\windows\build.ps1 first, a Python with numpy and Pillow
# ($env:PYTHON, Tools\venv, or python on the PATH) and ffmpeg (winget install Gyan.FFmpeg).
# Usage: scripts\windows\capture-reel.ps1 -Shot wireframe|fleet|physics|storm|night|all [-Quality master|draft]
#        [-Passes lit,wire] [-ComposeOnly] [-DryRun] [-Preflight] [-List]
# Output: Artifacts\reel\<shot>\<quality>\ (master.mov, <shot>.mp4/.webm/.jpg, meta.json; frames in loop\ and passes\).
param(
	[string]$Shot = '',
	[string]$Quality = 'master',
	[string]$Passes = '',
	[switch]$ComposeOnly,
	[switch]$DryRun,
	[switch]$Preflight,
	[switch]$List
)
. (Join-Path $PSScriptRoot 'env.ps1')
$env:UE_ROOT = $UERoot
$Py = if ($env:PYTHON) { $env:PYTHON } elseif (Test-Path (Join-Path $RepoRoot 'Tools\venv\Scripts\python.exe')) { Join-Path $RepoRoot 'Tools\venv\Scripts\python.exe' } else { 'python' }
if (-not (Get-Command $Py -ErrorAction SilentlyContinue)) { throw "No Python ($Py): install Python 3 or set `$env:PYTHON" }
$PyArgs = @((Join-Path $RepoRoot 'Tools\reel\capture_reel.py'))
if ($List) { $PyArgs += '--list' }
elseif ($Preflight) { $PyArgs += '--preflight' }
else {
	if (-not $Shot) { throw 'Give -Shot wireframe|fleet|physics|storm|night|all (or -List)' }
	$PyArgs += @($Shot, '--quality', $Quality)
	if ($Passes) { $PyArgs += @('--passes', $Passes) }
	if ($ComposeOnly) { $PyArgs += '--compose-only' }
	if ($DryRun) { $PyArgs += '--dry-run' }
}
& $Py @PyArgs
exit $LASTEXITCODE
