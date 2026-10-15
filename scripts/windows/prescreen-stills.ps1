# Pre-screen stills without packaging: the visual bench views (views.ps1) on each tier, run uncooked from the editor
# binary (run-game.ps1, about 30 s a still once the shaders are cached), so a visual change can be judged before any
# package. Frame rates from here mean nothing: measure fps on a package (bench-visual-win.ps1).
# Writes Artifacts\prescreen\<Label>\<view>-<tier>.png; -Compare <label> also writes <view>-<tier>-vs-<label>.png
# (the other label's still on the left, this one on the right).
# Usage: scripts\windows\prescreen-stills.ps1 -Label main [-View storm,beam8] [-Tiers High,Ultra]
#        scripts\windows\prescreen-stills.ps1 -Label slicks -View beam8 -Compare main
param(
	[string]$Label = 'prescreen',
	[string[]]$View = @(),
	[string[]]$Tiers = @('High', 'Ultra'),
	[int]$Seconds = 6,
	[int]$ResX = 1920,
	[int]$ResY = 1080,
	[string]$Compare = ''
)
. (Join-Path $PSScriptRoot 'env.ps1')
. (Join-Path $PSScriptRoot 'views.ps1')
$Tiers = @($Tiers | ForEach-Object { $_ -split ',' } | Where-Object { $_ })
$Names = @($View | ForEach-Object { $_ -split ',' } | Where-Object { $_ })
if (-not $Names) { $Names = @($Views.Keys) }
$Names = @($Names | Where-Object { $Views.Contains($_) })
$Dir = Join-Path $Artifacts "prescreen\$Label"
New-Item -ItemType Directory -Force -Path $Dir | Out-Null
$Bench = Join-Path $RepoRoot 'Saved\Bench'
Add-Type -AssemblyName System.Drawing

foreach ($Name in $Names) {
	foreach ($Q in $Tiers) {
		$Shot = "$Name-$($Q.ToLower())"
		$T = Get-Date
		& (Join-Path $PSScriptRoot 'run-game.ps1') -Seconds $Seconds -ResX $ResX -ResY $ResY -Shot $Shot `
			-GameArgs "$($Views[$Name]) -SailingQuality=$Q -SailingNoHud" | Out-Null
		$Png = Join-Path $Bench "$Shot.png"
		if (-not (Test-Path $Png)) { Write-Host ("{0,-14} {1,-6} no still (see Saved\Logs\SailingSim.log)" -f $Name, $Q) -ForegroundColor Red; continue }
		Copy-Item -Force $Png (Join-Path $Dir "$Shot.png")
		Write-Host ("{0,-14} {1,-6} {2,4:N0} s" -f $Name, $Q, ((Get-Date) - $T).TotalSeconds)
		$Other = Join-Path $Artifacts "prescreen\$Compare\$Shot.png"
		if ($Compare -and (Test-Path $Other)) {
			$A = [System.Drawing.Image]::FromFile($Other); $B = [System.Drawing.Image]::FromFile($Png)
			$Out = New-Object System.Drawing.Bitmap ($A.Width + $B.Width), ([Math]::Max($A.Height, $B.Height))
			$G = [System.Drawing.Graphics]::FromImage($Out)
			$G.DrawImage($A, 0, 0, $A.Width, $A.Height); $G.DrawImage($B, $A.Width, 0, $B.Width, $B.Height)
			$Out.Save((Join-Path $Dir "$Shot-vs-$Compare.png"), [System.Drawing.Imaging.ImageFormat]::Png)
			$G.Dispose(); $Out.Dispose(); $A.Dispose(); $B.Dispose()
		}
	}
}
Write-Host "Stills: $Dir"
