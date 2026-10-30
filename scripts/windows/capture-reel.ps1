# Renders one sim reel loop through Movie Render Queue (docs/sim-reel/README.md). Windows twin of scripts/capture-reel.sh:
# Tools\reel\capture_reel.py with the project's venv (numpy, Pillow). Run scripts\windows\build.ps1 first.
# Usage: scripts\windows\capture-reel.ps1 wireframe [-Quality master] [-Passes lit,wire] [-ComposeOnly] [-DryRun]
param(
	[Parameter(Mandatory = $true)][string]$Shot,
	[string]$Quality = 'master',
	[string]$Passes = '',
	[switch]$ComposeOnly,
	[switch]$DryRun
)
. (Join-Path $PSScriptRoot 'env.ps1')
$env:UE_ROOT = $UERoot
$Py = Join-Path $RepoRoot 'Tools\venv\Scripts\python.exe'
if (-not (Test-Path $Py)) { $Py = 'python' }
$PyArgs = @((Join-Path $RepoRoot 'Tools\reel\capture_reel.py'), $Shot, '--quality', $Quality)
if ($Passes) { $PyArgs += @('--passes', $Passes) }
if ($ComposeOnly) { $PyArgs += '--compose-only' }
if ($DryRun) { $PyArgs += '--dry-run' }
& $Py @Args
exit $LASTEXITCODE
