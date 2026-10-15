# Reproduces each scene of a scene list (scene,preset,args columns) with the capture mode on the packaged Windows game
# and copies the still, its camera settings and telemetry to -Out. Windows twin of scripts/capture-scenes.sh (which runs
# uncooked); package first (scripts\windows\package-win.ps1).
# Usage: scripts\windows\capture-scenes-win.ps1 [-Scenes docs\graphics-5\game\final.csv] [-Out docs\graphics-8\game]
#                                               [-Seconds 12] [-ResX 1440 -ResY 1080] [-Only game-01,game-04]
param(
	[string]$Scenes = '',
	[string]$Out = '',
	[int]$Seconds = 12,
	[int]$ResX = 1440,
	[int]$ResY = 1080,
	[string[]]$Only = @()
)
. (Join-Path $PSScriptRoot 'env.ps1')
if (-not $Scenes) { $Scenes = Join-Path $RepoRoot 'docs\graphics-5\game\final.csv' }
if (-not $Out) { $Out = Join-Path $RepoRoot 'docs\graphics-8\game' }
$Only = @($Only | ForEach-Object { $_ -split ',' } | Where-Object { $_ })
New-Item -ItemType Directory -Force -Path $Out | Out-Null

foreach ($Row in (Import-Csv $Scenes)) {
	if ($Only.Count -and $Only -notcontains $Row.scene) { continue }
	$GameArgs = "$($Row.args) -SailingCapture=$($Row.preset)"
	& (Join-Path $PSScriptRoot 'bench-win.ps1') -Seconds $Seconds -ResX $ResX -ResY $ResY -Shot $Row.scene -GameArgs $GameArgs | Out-Null
	foreach ($Ext in 'png', 'camera.json', 'telemetry.csv') {
		$F = Join-Path $Artifacts "$($Row.scene).$Ext"
		if (Test-Path $F) { Move-Item -Force $F (Join-Path $Out "$($Row.scene).$Ext") }
	}
	Write-Host ("{0}: {1}" -f $Row.scene, $(if (Test-Path (Join-Path $Out "$($Row.scene).png")) { 'ok' } else { 'FAILED' }))
}
