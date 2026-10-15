# Crew C2 on the PC: the body solve and everything after it (docs/crew-2/README.md).
#   1. (with -TestClip) renders test footage of the game's own helm playing a synthetic clip (make_test_footage.py),
#   2. solves each clip's frames with MetaHuman Animator's markerless body solve (solve_clips.py, a full editor: the
#      solve needs the GPU, which a -run=pythonscript commandlet doesn't have),
#   3. carries the solves to the crew (capture_clips.py) and runs SailingSim.Visual.CrewCapture.
# Build first. Usage:
#   scripts\windows\capture-solve.ps1                        Bean's clips: frames in D:\dev\capture\frames\<clip>\
#   scripts\windows\capture-solve.ps1 -Footage <dir> -Fps 60
#   scripts\windows\capture-solve.ps1 -TestClip tack_port    renders and solves the test clip (Saved\CaptureTest)
param(
	[string]$Footage = 'D:\dev\capture\frames',
	[int]$Fps = 30,
	[string]$Only = '',
	[string]$TestClip = '',
	[switch]$Resolve
)
. (Join-Path $PSScriptRoot 'env.ps1')
$Editor = Join-Path $UERoot 'Engine\Binaries\Win64\UnrealEditor.exe'
$Capture = (Join-Path $RepoRoot 'Tools\capture') -replace '\\', '/'

# A full editor that runs one script and quits when it's done (-ExecutePythonScript); returns the exit code.
function Invoke-EditorScript([string]$Line, [string]$Map, [string]$Name) {
	$Log = Join-Path $Artifacts "$Name.log"
	$A = "`"$Project`" $Map -ExecutePythonScript=`"$Line`" -unattended -NoCrashReporter -nosplash -nosound -NoP4 -abslog=`"$Log`""
	$P = Start-Process $Editor -ArgumentList $A -PassThru
	$null = $P.Handle
	$P.WaitForExit()
	Select-String -Path $Log -Pattern 'LogPython: (Error: )?(TestFootage|Solve|Capture):' | ForEach-Object { Write-Host ($_.Line -replace '^.*LogPython: ', '') }
	if (Select-String -Path $Log -Pattern 'LogPython: Error: Traceback') { Write-Host "$Name failed; see $Log" -ForegroundColor Red; exit 1 }
	return $P.ExitCode
}

if ($TestClip) {
	$env:CAPTURE_CLIP = $TestClip
	$env:CAPTURE_FPS = "$Fps"
	$env:CAPTURE_SYNTHETIC = '1'   # the stance clip the test footage plays
	& (Join-Path $PSScriptRoot 'run-python.ps1') 'Tools\capture\capture_clips.py' | Out-Null
	Remove-Item Env:CAPTURE_SYNTHETIC
	& (Join-Path $PSScriptRoot 'run-python.ps1') 'Tools\capture\make_test_footage.py' -ScriptArgs 'stage'
	if ($LASTEXITCODE -ne 0) { exit 1 }
	$null = Invoke-EditorScript "$Capture/make_test_footage.py render" '/Game/Crew/Capture/Test/L_Stage' 'make_test_footage_render'
	$Footage = Join-Path $RepoRoot 'Saved\CaptureTest'
	$Only = $TestClip
}

$env:CAPTURE_FOOTAGE = $Footage
$env:CAPTURE_FPS = "$Fps"
$env:CAPTURE_ONLY = $Only
$env:CAPTURE_RESOLVE = if ($Resolve -or $TestClip) { '1' } else { '' }
$null = Invoke-EditorScript "$Capture/solve_clips.py" '' 'solve_clips'

& (Join-Path $PSScriptRoot 'run-python.ps1') 'Tools\capture\capture_clips.py'
if ($LASTEXITCODE -ne 0) { exit 1 }
& (Join-Path $PSScriptRoot 'test.ps1') -Filter 'SailingSim.Visual.CrewCapture'
exit $LASTEXITCODE
