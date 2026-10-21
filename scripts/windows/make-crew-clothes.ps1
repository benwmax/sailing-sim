# The crew's scripted clothing on Windows. Windows twin of scripts/make-crew-clothes.sh (keep them in step): exports
# each MetaHuman body and outfit (scripts/export_crew_bodies.py, full editor with the MetaHumanCharacter plugin), tailors
# the polo, deck shoes and life jacket in Blender headless (Tools/blender/build_polo.py, build_shoes.py, build_vest.py ->
# Artifacts\crew\*.fbx), imports them (scripts/import_crew_clothes.py; $env:PIECES=Vest imports only the vests) and turns
# on the faces' skin detail (scripts/tune_crew_skin.py). Needs the MetaHumans (git-ignored, from the Mac's
# scripts/pack-metahumans.sh) and Blender. Logs in Artifacts\crew-*.log. Build the editor first.
# Usage: scripts\windows\make-crew-clothes.ps1 [-SkipExport] [-ExportOnly]     ($env:SKIP_EXPORT / EXPORT_ONLY = 1 too)
#   Blender: $env:BLENDER, else the newest under C:\Program Files\Blender Foundation.
param(
	[switch]$SkipExport,
	[switch]$ExportOnly
)
. (Join-Path $PSScriptRoot 'env.ps1')
if ($env:SKIP_EXPORT -eq '1') { $SkipExport = $true }
if ($env:EXPORT_ONLY -eq '1') { $ExportOnly = $true }
$Crew = Join-Path $Artifacts 'crew'
New-Item -ItemType Directory -Force -Path $Crew | Out-Null
$Roles = 'Helm', 'Trimmer', 'Bow'

if (-not $SkipExport) {
	# The export ends the editor with os._exit, which can cut the log before its "Crew bodies" lines, so the FBX files
	# written after the start are the proof of the export.
	$Start = Get-Date
	$Editor = Join-Path $UERoot 'Engine\Binaries\Win64\UnrealEditor.exe'
	$Script = (Join-Path $RepoRoot 'scripts\export_crew_bodies.py') -replace '\\', '/'
	Invoke-Tool $Editor "`"$Project`" -EnablePlugins=MetaHumanCharacter -ExecCmds=`"py $Script`" -unattended -NoCrashReporter -nosplash -NoP4 -stdout" (Join-Path $Artifacts 'crew-export.log') | Out-Null
	foreach ($Role in $Roles) {
		foreach ($Part in 'Body', 'Outfit') {
			$Fbx = Join-Path $Crew "$($Role)_$Part.fbx"
			if (-not (Test-Path $Fbx) -or (Get-Item $Fbx).LastWriteTime -lt $Start) { throw "Crew bodies: $Role $Part not exported (see Artifacts\crew-export.log)" }
		}
	}
	Write-Host "Crew bodies: 6 FBX exported to $Crew"
}
if ($ExportOnly) { exit 0 }

$Blender = if ($env:BLENDER) { $env:BLENDER } else { (Get-ChildItem 'C:\Program Files\Blender Foundation\*\blender.exe' | Sort-Object FullName | Select-Object -Last 1).FullName }
function Run-Blender([string]$Script, [string]$ScriptArgs, [string]$Log, [string]$Tag) {
	$C = Invoke-Tool $Blender "-b --factory-startup -noaudio -P `"$RepoRoot\Tools\blender\$Script`" -- $ScriptArgs" (Join-Path $Artifacts $Log) | Select-Object -Last 1
	if ($C -ne 0) { Get-Content (Join-Path $Artifacts $Log) -Tail 30; throw "Blender $Script failed; see Artifacts\$Log" }
	Select-String -Path (Join-Path $Artifacts $Log) -Pattern "^$($Tag):" | ForEach-Object { $_.Line }
}
foreach ($Role in $Roles) {
	$P = { param($Name) "`"$(Join-Path $Crew "$($Role)_$Name.fbx")`"" }
	Run-Blender 'build_polo.py' "$(& $P 'Outfit') $(& $P 'Polo')" "crew-blender-$Role.log" 'Polo'
	Run-Blender 'build_shoes.py' "$(& $P 'Body') $(& $P 'Shoes')" "crew-shoes-$Role.log" 'Shoes'
	# Graphics G6: the life jacket tailored over the polo; G8: and the polo with its torso under the vest cut away.
	Run-Blender 'build_vest.py' "$(& $P 'Polo') $(& $P 'Vest') $(& $P 'PoloOpen')" "crew-vest-$Role.log" 'Vest'
}

function Run-EditorPython([string]$Script, [string]$Log, [string]$Pattern) {
	$Path = (Join-Path $RepoRoot "scripts\$Script") -replace '\\', '/'
	Invoke-Tool $EditorCmd "`"$Project`" -run=pythonscript -script=`"$Path`" -unattended -NoCrashReporter -nosplash -nosound -NoP4 -stdout -FullStdOutLogOutput" (Join-Path $Artifacts $Log) | Out-Null
	Select-String -Path (Join-Path $Artifacts $Log) -Pattern $Pattern | ForEach-Object { $_.Line -replace '.*LogPython: ', '' }
}
Run-EditorPython 'import_crew_clothes.py' 'crew-import.log' 'Crew clothes'
# Graphics G8: the faces' micro skin detail and pores (the optimized build leaves them off).
Run-EditorPython 'tune_crew_skin.py' 'crew-skin.log' 'Crew skin' | Select-Object -Last 1
