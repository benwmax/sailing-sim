# Cannon fire's effects on the PC (docs/cannon-fire/), the twin of scripts/make-cannon-fx.sh: the textures
# (Tools/shipkit/frigate/make_cannon_textures.py into Artifacts\cannon-fx), then import_cannon_fx.py in the editor
# (M_CannonSmoke, M_CannonFlash). Build first. -TexturesOnly skips the editor.
param([switch]$TexturesOnly)
. (Join-Path $PSScriptRoot 'env.ps1')
$Out = Join-Path $Artifacts 'cannon-fx'
$Py = Join-Path $RepoRoot 'Tools\venv\Scripts\python.exe'
if (-not (Test-Path $Py)) { $Py = 'python' }
& $Py -I (Join-Path $RepoRoot 'Tools\shipkit\frigate\make_cannon_textures.py') $Out --preview
if ($LASTEXITCODE -ne 0) { throw 'make_cannon_textures.py failed' }
if ($TexturesOnly) { exit 0 }
& (Join-Path $PSScriptRoot 'run-python.ps1') import_cannon_fx.py -ScriptArgs ($Out -replace '\\', '/')
exit $LASTEXITCODE
