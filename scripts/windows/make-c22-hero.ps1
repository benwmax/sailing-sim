# Catalina 22 rebuild, game wiring (docs/c22-12). Windows twin of scripts/make-c22-hero.sh: builds the rebuild's model
# (Tools/shipkit/catalina22/build_c22.py), cuts it into the game's parts (export_game_c22.py -> Artifacts\models\SM_C22Hero_*.fbx
# and C22Hero_sockets.json) and imports them to /Game/Boats/C22Hero (scripts/import_boats.py c22hero). Build the editor and
# run make_materials.py first (the boat library).
# Usage: scripts\windows\make-c22-hero.ps1 [-Rebuild] [-NoImport]
#   -Rebuild: build the .blend again even when it exists (it takes about 2 min). Blender: $env:BLENDER, else the newest
#   under C:\Program Files\Blender Foundation.
param(
	[switch]$Rebuild,
	[switch]$NoImport
)
. (Join-Path $PSScriptRoot 'env.ps1')
$Models = Join-Path $Artifacts 'models'
$Build = Join-Path $Artifacts 'c22-build'
New-Item -ItemType Directory -Force -Path $Models, $Build | Out-Null
$Src = Join-Path $RepoRoot 'Tools\shipkit\catalina22'
$Blender = if ($env:BLENDER) { $env:BLENDER } else { (Get-ChildItem 'C:\Program Files\Blender Foundation\*\blender.exe' | Sort-Object FullName | Select-Object -Last 1).FullName }
function Run-Blender([string]$Script, [string]$ScriptArgs, [string]$Log) {
	$C = Invoke-Tool $Blender "-b --factory-startup -noaudio -P `"$Src\$Script`" -- $ScriptArgs" (Join-Path $Artifacts $Log) | Select-Object -Last 1
	if ($C -ne 0) { throw "Blender $Script failed; see Artifacts\$Log" }
	Select-String -Path (Join-Path $Artifacts $Log) -Pattern '^C22' | ForEach-Object { $_.Line }
}
if ($Rebuild -or -not (Test-Path (Join-Path $Build 'c22.blend'))) { Run-Blender 'build_c22.py' "`"$Build`"" 'blender-c22.log' }
Run-Blender 'export_game_c22.py' "`"$Build`" `"$Models`"" 'blender-c22hero.log'
if ($NoImport) { exit 0 }
& (Join-Path $PSScriptRoot 'run-python.ps1') -Script import_boats.py -ScriptArgs 'c22hero'
exit $LASTEXITCODE
