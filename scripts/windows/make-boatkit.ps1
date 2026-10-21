# Boat kit on the PC (boat fidelity 2, docs/boat-fidelity-2): the trim sheet, the kit (hero and light FBX per part, kit.json)
# and, with -Render, the review renders and sheets, then (with -Import) the Unreal import into /Game/Boats/Kit.
# Windows twin of scripts/make-boatkit.sh's kit step (the boat dressing stays on the Mac script). Needs Blender 4.2 and a
# Python with numpy and Pillow.
# Usage: scripts\windows\make-boatkit.ps1 [-Render] [-Import] [-Docs]   (-Docs writes the review JPEGs to docs/boat-fidelity-2)
param([switch]$Render, [switch]$Import, [switch]$Docs)
. (Join-Path $PSScriptRoot 'env.ps1')
$Blender = if ($env:BLENDER) { $env:BLENDER } else { (Get-ChildItem 'C:\Program Files\Blender Foundation' -Filter blender.exe -Recurse -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1).FullName }
if (-not $Blender) { throw 'No Blender: install it or set $env:BLENDER' }
$Python = if ($env:PYTHON) { $env:PYTHON } else { 'python' }
$Kit = Join-Path $RepoRoot 'Tools\boatkit'
$Out = Join-Path $Artifacts 'boatkit\kit'
New-Item -ItemType Directory -Force $Out | Out-Null
& $Python (Join-Path $Kit 'make_trim_sheet.py')
if ($LASTEXITCODE) { throw 'make_trim_sheet.py failed' }
$KitArgs = @('-b', '--factory-startup', '-noaudio', '-P', (Join-Path $Kit 'build_kit.py'), '--', $Out)
if ($Render) { $KitArgs += '--render' }
& $Blender @KitArgs *> (Join-Path $Artifacts 'boatkit\kit.log')
if (-not (Select-String -Quiet -Path (Join-Path $Artifacts 'boatkit\kit.log') -Pattern '^Kit: \d+ parts') -or (Select-String -Quiet -Path (Join-Path $Artifacts 'boatkit\kit.log') -Pattern 'Traceback')) {
	Get-Content (Join-Path $Artifacts 'boatkit\kit.log') -Tail 30
	throw 'build_kit.py failed'
}
Select-String -Path (Join-Path $Artifacts 'boatkit\kit.log') -Pattern '^Kit: \d+ parts' | ForEach-Object { $_.Line }
if ($Render) {
	$SheetArgs = @((Join-Path $Kit 'make_review_sheet.py'), $Out)
	if ($Docs) { $SheetArgs += (Join-Path $RepoRoot 'docs\boat-fidelity-2') }
	& $Python @SheetArgs
}
if ($Import) {
	& (Join-Path $PSScriptRoot 'run-python.ps1') import_hardware_kit.py
	if ($LASTEXITCODE) { throw 'import_hardware_kit.py failed' }
}
