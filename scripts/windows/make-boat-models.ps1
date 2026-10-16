# Regenerates the boat models on Windows. Windows twin of scripts/make-boat-models.sh: exports the physics geometry
# (Tools/BoatExport, standalone C++, built with MSVC), builds the models in Blender headless (Tools/blender/build_*.py ->
# Artifacts\models\*.fbx), then imports them with scripts/import_boats.py. Build the editor first.
# Usage: scripts\windows\make-boat-models.ps1 [-Parts fleet,j22,gear,berthed] [-Fleet Sunfish,Catalina30] [-NoImport]
#   -Parts: what to rebuild (default: all). -Fleet narrows the fleet to some classes.
#   Blender: $env:BLENDER, else the newest under C:\Program Files\Blender Foundation.
param(
	[string[]]$Parts = @('fleet', 'j22', 'gear', 'berthed'),
	[string[]]$Fleet = @('Sunfish', 'ILCA7', 'Catalina22', 'Catalina30', 'Hobie16', 'Corsair880', 'Lagoon42'),
	[switch]$NoImport
)
. (Join-Path $PSScriptRoot 'env.ps1')
$Parts = @($Parts | ForEach-Object { $_ -split ',' } | Where-Object { $_ })
$Fleet = @($Fleet | ForEach-Object { $_ -split ',' } | Where-Object { $_ })
$Models = Join-Path $Artifacts 'models'
New-Item -ItemType Directory -Force -Path $Models | Out-Null

# The exporter: SailingPhysics + Tools/BoatExport/main.cpp, with MSVC from the newest Visual Studio.
$VsWhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
$Vs = & $VsWhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
$VcVars = Join-Path $Vs 'VC\Auxiliary\Build\vcvars64.bat'
$Src = Join-Path $RepoRoot 'Source\SailingPhysics'
$Cpp = (Get-ChildItem (Join-Path $Src 'Private\*.cpp') | Where-Object { $_.Name -ne 'SailingPhysicsModule.cpp' } | ForEach-Object { "`"$($_.FullName)`"" }) -join ' '
$Exe = Join-Path $Artifacts 'boat-export.exe'
$Obj = Join-Path $Artifacts 'boat-export-obj'
New-Item -ItemType Directory -Force -Path $Obj | Out-Null
$Cl = "cl /nologo /std:c++17 /O2 /EHsc /W3 /I`"$Src\Public`" $Cpp `"$RepoRoot\Tools\BoatExport\main.cpp`" /Fo`"$Obj/`" /Fe`"$Exe`""
$Code = Invoke-Tool $env:ComSpec "/d /s /c `"`"$VcVars`" >nul && $Cl`"" (Join-Path $Artifacts 'boat-export-build.log') | Select-Object -Last 1
if (-not (Test-Path $Exe)) { throw "boat-export did not build; see Artifacts\boat-export-build.log" }

$Blender = if ($env:BLENDER) { $env:BLENDER } else { (Get-ChildItem 'C:\Program Files\Blender Foundation\*\blender.exe' | Sort-Object FullName | Select-Object -Last 1).FullName }
function Run-Blender([string]$Script, [string]$ScriptArgs, [string]$Log) {
	$C = Invoke-Tool $Blender "-b --factory-startup -noaudio -P `"$RepoRoot\Tools\blender\$Script`" -- $ScriptArgs" (Join-Path $Artifacts $Log) | Select-Object -Last 1
	if ($C -ne 0) { throw "Blender $Script failed; see Artifacts\$Log" }
}
function Export-Boat([string]$Key) {
	& $Exe $Key (Join-Path $Models "$Key.json")
	if ($LASTEXITCODE -ne 0) { throw "boat-export $Key failed" }
}

if ($Parts -contains 'j22' -or $Parts -contains 'berthed') { Export-Boat 'j22' }
if ($Parts -contains 'j22') {
	Run-Blender 'build_j22.py' "`"$Models\j22.json`" `"$Models`"" 'blender-j22.log'
	Run-Blender 'build_crew.py' "`"$Models`"" 'blender-crew.log'
}
if ($Parts -contains 'gear') { Run-Blender 'build_crew_gear.py' "`"$Models`"" 'blender-gear.log' }
$Keys = @{ Sunfish = 'sunfish'; ILCA7 = 'ilca7'; Catalina22 = 'catalina22'; Catalina30 = 'catalina30'; Hobie16 = 'hobie16'; Corsair880 = 'corsair880'; Lagoon42 = 'lagoon42' }
if ($Parts -contains 'fleet') {
	foreach ($Tag in $Fleet) {
		Export-Boat $Keys[$Tag]
		Run-Blender 'build_fleet.py' "`"$Models\$($Keys[$Tag]).json`" $Tag `"$Models`"" "blender-$Tag.log"
		Select-String -Path (Join-Path $Artifacts "blender-$Tag.log") -Pattern "^$($Tag): LOA" | ForEach-Object { $_.Line }
	}
}
if ($Parts -contains 'berthed') {
	foreach ($K in 'catalina22', 'catalina30') { if (-not (Test-Path (Join-Path $Models "$K.json"))) { Export-Boat $K } }
	foreach ($V in 0..5) {
		foreach ($Pair in @(@('J22', 'j22'), @('Catalina22', 'catalina22'), @('Catalina30', 'catalina30'))) {
			Run-Blender 'build_berthed.py' "$($Pair[0]) `"$Models\$($Pair[1]).json`" `"$Models`" $V" "blender-berthed-$($Pair[0])-$V.log"
		}
	}
}
if ($NoImport) { exit 0 }
# import_boats.py, one run per part asked for: `fleet` (the seven fleet boats), `j22only`, `gearonly`, `dress` (the
# keelboats' berthed dresses). The old single run passed `dress` whenever berthed was asked for, and that branch
# imports only what its flags name, so `-Parts j22,berthed` (and the default, every part) never re-imported the J/22.
$Runs = @()
if ($Parts -contains 'fleet') { $Runs += 'fleet' }
if ($Parts -contains 'j22') { $Runs += 'j22only' }
if ($Parts -contains 'gear') { $Runs += 'gearonly' }
if ($Parts -contains 'berthed') { $Runs += 'dress' }
foreach ($R in $Runs) { & (Join-Path $PSScriptRoot 'run-python.ps1') -Script import_boats.py -ScriptArgs $R }
exit $LASTEXITCODE
