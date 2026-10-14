# Compiles the editor target (game + physics + tests modules) with UnrealBuildTool. Windows twin of scripts/build.sh.
# Usage: scripts\windows\build.ps1 [-Config Development|DebugGame]     Log: Artifacts\build.log
param([ValidateSet('Development', 'DebugGame')][string]$Config = 'Development')
. (Join-Path $PSScriptRoot 'env.ps1')

$Code = Invoke-Tool $UBTBuild "SailingSimEditor Win64 $Config -Project=`"$Project`" -WaitMutex -NoHotReload" (Join-Path $Artifacts 'build.log')
if ($Code -ne 0) { Write-Host "Build failed (exit $Code). See Artifacts\build.log" -ForegroundColor Red }
exit $Code
