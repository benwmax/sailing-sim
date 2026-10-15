# Shared paths and helpers for the Windows scripts (dot-sourced by each). The Windows twin of scripts/env.sh.
# Override UE_ROOT if Unreal lives elsewhere: $env:UE_ROOT = 'D:\Epic Games\UE_5.8'
# Written for Windows PowerShell 5.1 (the one that ships with Windows) and PowerShell 7.
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Project = Join-Path $RepoRoot 'SailingSim.uproject'
$UERoot = if ($env:UE_ROOT) { $env:UE_ROOT } else { 'C:\Program Files\Epic Games\UE_5.8' }
$UBTBuild = Join-Path $UERoot 'Engine\Build\BatchFiles\Build.bat'
$RunUAT = Join-Path $UERoot 'Engine\Build\BatchFiles\RunUAT.bat'
$EditorCmd = Join-Path $UERoot 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe'
$Artifacts = Join-Path $RepoRoot 'Artifacts'
$Packaged = Join-Path $RepoRoot 'Packaged'

if (-not (Test-Path $EditorCmd)) {
	throw "Unreal Engine not found at $UERoot (set `$env:UE_ROOT to the folder that holds Engine\)"
}
New-Item -ItemType Directory -Force -Path $Artifacts | Out-Null

# Prints whatever was appended to a file since byte $Pos; returns the new position. The file stays shared, so the
# tool writing it is never blocked.
function Show-NewOutput([string]$Path, [long]$Pos) {
	if (-not (Test-Path $Path)) { return $Pos }
	$Stream = [System.IO.File]::Open($Path, 'Open', 'Read', 'ReadWrite')
	try {
		if ($Stream.Length -le $Pos) { return $Pos }
		$null = $Stream.Seek($Pos, 'Begin')
		$Reader = New-Object System.IO.StreamReader($Stream)
		$Text = $Reader.ReadToEnd()
		if ($Text) { [Console]::Out.Write($Text) }
		return $Stream.Length
	} finally { $Stream.Dispose() }
}

# Runs a tool with a raw argument string (quote paths yourself), streams its output to the console and to $Log,
# and returns its exit code. A raw string, because PowerShell 5.1 re-quotes array arguments that hold spaces,
# which breaks Unreal's -ExecCmds="a; b" style arguments.
function Invoke-Tool([string]$Exe, [string]$Arguments, [string]$Log) {
	$Err = "$Log.stderr"
	if ($Exe -match '\.(bat|cmd)$') {
		# Batch files run through cmd. Wrap the whole line in one more pair of quotes with /s, or cmd strips the first
		# and last quote of `"C:\Program Files\...\Build.bat" ... -Project="..."` and fails on "C:\Program".
		$Arguments = "/d /s /c `"`"$Exe`" $Arguments`""
		$Exe = $env:ComSpec
	}
	Remove-Item -Force -ErrorAction SilentlyContinue $Log, $Err
	$P = Start-Process -FilePath $Exe -ArgumentList $Arguments -NoNewWindow -PassThru `
		-RedirectStandardOutput $Log -RedirectStandardError $Err
	$null = $P.Handle   # keeps the exit code readable after the process ends (a Start-Process quirk)
	$Pos = 0
	while ($true) {
		$Done = $P.HasExited
		$Pos = Show-NewOutput $Log $Pos
		if ($Done) { break }
		Start-Sleep -Milliseconds 1000
	}
	$P.WaitForExit()
	if ((Test-Path $Err) -and (Get-Item $Err).Length -gt 0) {
		$ErrText = Get-Content -Raw $Err
		[Console]::Out.Write($ErrText)
		Add-Content -Path $Log -Value $ErrText
	}
	Remove-Item -Force -ErrorAction SilentlyContinue $Err
	return $P.ExitCode
}

# What a step reads, by content (scripts/gate.sh's inputs_hash, so the PC and the Mac skip the same way): each file's git
# blob id under $Paths, uncommitted and new files hashed the same way, so a commit of the same files changes nothing.
# Returns 16 hex digits.
function Get-InputsHash([string[]]$Paths) {
	Push-Location $RepoRoot
	try {
		$Blobs = @{}
		foreach ($L in (git ls-files -s -- @Paths)) {
			$Meta, $Path = $L -split "`t", 2
			$Blobs[$Path] = ($Meta -split ' ')[1]
		}
		$Changed = @(git ls-files -m -o --exclude-standard -- @Paths | Where-Object { $_ })
		$Present = @($Changed | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf })
		if ($Present) {
			$Ids = @($Present | git hash-object --stdin-paths)
			for ($I = 0; $I -lt $Present.Count; $I++) { $Blobs[$Present[$I]] = $Ids[$I] }
		}
		foreach ($P in $Changed) { if (-not (Test-Path -LiteralPath $P -PathType Leaf)) { $Blobs.Remove($P) } }
		$Keys = [string[]]@($Blobs.Keys); [Array]::Sort($Keys, [StringComparer]::Ordinal)   # as Python sorts
		$Text = ($Keys | ForEach-Object { "$($Blobs[$_]) $_`n" }) -join ''
		$Hash = [System.Security.Cryptography.SHA1]::Create().ComputeHash([System.Text.Encoding]::UTF8.GetBytes($Text))
		return ([System.BitConverter]::ToString($Hash).Replace('-', '').ToLower()).Substring(0, 16)
	} finally { Pop-Location }
}

# The folder the packaged game writes Saved\ to: next to the game in Development and Test builds, under
# %LOCALAPPDATA% in some Shipping setups. Returns every candidate; callers use the one that has the file.
function Get-SavedDirs {
	@(
		(Join-Path $Packaged 'Windows\SailingSim\Saved'),
		(Join-Path $env:LOCALAPPDATA 'SailingSim\Saved')
	)
}
