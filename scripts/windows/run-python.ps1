# Runs one of the repo's editor Python scripts headless (UnrealEditor-Cmd -run=pythonscript): the Windows way to run
# make_materials.py, make_lake_map.py, bake_shore.py, import_world.py and friends (the Mac wraps them in make-content.sh,
# make-world-models.sh, bake-shore.sh). Build first. Fails on a Python traceback.
# Usage: scripts\windows\run-python.ps1 make_materials.py [-ScriptArgs "GalvestonBay"] [-Only build_boat_library,build_world_surface]
#   -Only sets MATERIALS_ONLY (make_materials.py rebuilds just those functions).
param(
	[Parameter(Mandatory = $true)][string]$Script,
	[string]$ScriptArgs = '',
	[string]$Only = ''
)
. (Join-Path $PSScriptRoot 'env.ps1')
$Path = if ([System.IO.Path]::IsPathRooted($Script)) { $Script } elseif (Test-Path (Join-Path $RepoRoot $Script)) { Join-Path $RepoRoot $Script } else { Join-Path $RepoRoot "scripts\$Script" }
if (-not (Test-Path $Path)) { throw "No script at $Path" }
if ($Only) { $env:MATERIALS_ONLY = $Only } else { Remove-Item Env:MATERIALS_ONLY -ErrorAction SilentlyContinue }
$Name = [System.IO.Path]::GetFileNameWithoutExtension($Path)
$Log = Join-Path $Artifacts "$Name.log"
$Line = ($Path -replace '\\', '/') + $(if ($ScriptArgs) { " $ScriptArgs" } else { '' })
$Code = Invoke-Tool $EditorCmd "`"$Project`" -run=pythonscript -script=`"$Line`" -unattended -NoCrashReporter -nosplash -nosound -NoP4 -stdout -FullStdOutLogOutput" $Log | Select-Object -Last 1
# (Not the callstack of the editor's crash at shutdown after a big import, which scripts end with os._exit to dodge.)
if (Select-String -Path $Log -Pattern 'Traceback|Error: .*(Python|compil)' | Where-Object { $_.Line -notmatch '\[Callstack\]' }) {
	Select-String -Path $Log -Pattern 'Traceback|Error: ' -Context 0, 8 | Select-Object -First 6 | ForEach-Object { $_.ToString() }
	Write-Host "$Name failed; see $Log" -ForegroundColor Red
	exit 1
}
Write-Host "$Name done (editor exit $Code); log $Log"
exit 0
