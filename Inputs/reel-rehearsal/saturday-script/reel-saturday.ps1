# SATURDAY CAPTURE (local, not pushed). Usage: reel-saturday.ps1 -Package Windows-<freeze sha> [-Only P1-wireframe,R05-tack-orbit] [-Res 4k|1080p]
# Each take via rec.ps1 (Bean's Saved held per run), frames to D:\dev\reel\saturday-<package>\<take>. Args from the dry run
# (Inputs/reel-rehearsal/dryrun-83aa7652/notes.md): R01 at 7.4, R05 warm-up 11.5, R06 helpful HUD, P3 TWA 90; R13 left out (jib stowed at the dock).
# Frames to D:\dev\reel\dryrun\<shot>. Shot files from Inputs/reel-rehearsal/shots (inputs 88f5917e). Results in Artifacts\bench\dryrun-83aa7652\.
param([Parameter(Mandatory)][string]$Package, [string[]]$Only, [ValidateSet('4k', '1080p')][string]$Res = '4k', [switch]$ViewModeArg)
$B = 'D:\dev\ss-fix\Artifacts\bench'; $r = "$B\rec.ps1"; $Out = "$B\saturday-$Package"; New-Item -ItemType Directory -Force $Out | Out-Null
function Note([string]$t) { Add-Content "$Out\status.txt" ("{0:yyyy-MM-dd HH:mm:ss} {1}" -f (Get-Date), $t) }
$shots = @{}
foreach ($f in Get-ChildItem 'D:\dev\ss-inputs-821b\Inputs\reel-rehearsal\shots' -Filter '*.json' -ErrorAction SilentlyContinue) { $shots[$f.BaseName] = (Get-Content $f.FullName -Raw).Trim() }
if (-not $shots.Count) { foreach ($n in (git -C D:\dev\ss-inputs-821b ls-tree --name-only origin/inputs Inputs/reel-rehearsal/shots/)) { $shots[[IO.Path]::GetFileNameWithoutExtension($n)] = (git -C D:\dev\ss-inputs-821b show "origin/inputs:$n") -join '' } }
$P = $Package; $RD = "saturday-$Package"; $rx = if ($Res -eq '4k') { 3840 } else { 1920 }; $ry = if ($Res -eq '4k') { 2160 } else { 1080 }
$lake = '-SailingWorld=Lake'
$jobs = [ordered]@{
	'P1-final'       = @{ shot = 'p1-layer-peel-orbit'; rec = 12; extra = "$lake -SailingWeather=AfternoonBreeze -SailingWind=12 -SailingHour=16 -SailingDemo -SailingTWA=60 -SailingHoldTWA=60" }
	'P1-lightingonly' = @{ shot = 'p1-layer-peel-orbit'; rec = 12; extra = "$lake -SailingWeather=AfternoonBreeze -SailingWind=12 -SailingHour=16 -SailingDemo -SailingTWA=60 -SailingHoldTWA=60 -DPCVars=r.ForceDebugViewModes=1 $(if ($ViewModeArg) { '-SailingViewMode=lightingonly' } else { '"-ExecCmds=viewmode lightingonly"' })" }
	'P1-wireframe'   = @{ shot = 'p1-layer-peel-orbit'; rec = 12; extra = "$lake -SailingWeather=AfternoonBreeze -SailingWind=12 -SailingHour=16 -SailingDemo -SailingTWA=60 -SailingHoldTWA=60 -DPCVars=r.ForceDebugViewModes=1 $(if ($ViewModeArg) { '-SailingViewMode=wireframe' } else { '`"-ExecCmds=viewmode wireframe`"' })" }
	'P2-storm'       = @{ nopath = $true; rec = 600; interval = '0.75'; timeout = 3600; extra = "$lake -SailingWeather=Thunderstorm -SailingStormDelay=60 -SailingHour=16 -SailingDemo -SailingTWA=60 -SailingHoldTWA=60 -SailingCapture=Tripod `"-SailingTripod=60,2.5,40,0.4`"" }
	'P3-realday'     = @{ nopath = $true; rec = 600; interval = '2'; timeout = 3600; extra = "$lake -SailingDay=2023-06-11 -SailingHour=18.892 -SailingDemo -SailingTWA=90 -SailingHoldTWA=90 -SailingCapture=Tripod `"-SailingTripod=60,2.5,40,0.4`"" }
	'P4-topdown'     = @{ shot = 'p4-topdown'; rec = 0.0166667; extra = "$lake -SailingWeather=ClearMistral -SailingWind=10 -SailingHour=12 `"-SailingStartAt=6500,-1750,0`"" }
	'P5-then-now'    = @{ shot = 'p5-then-now'; rec = 0.0166667; warm = 25; extra = "$lake -SailingWeather=AfternoonBreeze -SailingWind=13 -SailingWindFrom=182 -SailingHour=15 -SailingDemo -SailingTWA=-46 -SailingHoldTWA=-46 `"-SailingStartAt=630,-560,228`" $(if ($ViewModeArg) { '-SailingNoHullClip' })" }
	'R01-dawn-marina' = @{ shot = 's01-dawn-marina'; rec = 6; extra = "$lake -SailingDrill=LeavetheDock -SailingWeather=CalmMorning -SailingHour=7.4" }
	'R05-tack-orbit' = @{ shot = 's05-tack-orbit'; rec = 7; warm = 11.5; extra = "$lake -SailingLaunch=1 -SailingWeather=AfternoonBreeze -SailingWind=12 -SailingHour=15 -SailingDemo -SailingTWA=45" }
	'R06-helm-eye'   = @{ shot = 's06-helm-eye'; rec = 6; hud = $true; extra = "$lake -SailingLaunch=1 -SailingUiMode=helpful -SailingWeather=AfternoonBreeze -SailingWind=12 -SailingHour=15 -SailingDemo -SailingTWA=45 -SailingHoldTWA=45" }
	'R09-polar-chase' = @{ shot = 's09-polar-chase'; rec = 8; extra = "$lake -SailingLaunch=1 -SailingWeather=AfternoonBreeze -SailingWind=15 -SailingHour=14 -SailingDemo -SailingTWA=90 -SailingHoldTWA=90" }
	'R10-gust'       = @{ nopath = $true; rec = 7; extra = "$lake -SailingLaunch=1 `"-SailingBoat=Catalina 22`" -SailingWeather=AfternoonBreeze -SailingWind=14 -SailingHour=14 -SailingDemo -SailingTWA=60 -SailingHoldTWA=60 -SailingCapture=Tripod `"-SailingTripod=120,3,18,0.4`"" }
	'R12-sunfish'    = @{ shot = 's12-sunfish-bow'; rec = 8; extra = "$lake -SailingLaunch=0 -SailingBoat=Sunfish -SailingWeather=AfternoonBreeze -SailingWind=6 -SailingHour=14 -SailingDemo -SailingTWA=50" }
	'R13-jibclew'    = @{ shot = 's13b-jibclew-underway'; rec = 3; extra = "$lake -SailingLaunch=1 -SailingWeather=AfternoonBreeze -SailingWind=10 -SailingHour=14 -SailingDemo -SailingTWA=90 -SailingHoldTWA=90" }
	'R14-c22-dolly'  = @{ shot = 's14-c22-dolly'; rec = 7; extra = "$lake -SailingLaunch=1 `"-SailingBoat=Catalina 22`" -SailingWeather=AfternoonBreeze -SailingWind=12 -SailingHour=14 -SailingDemo -SailingTWA=90 -SailingHoldTWA=90" }
	'R21-golden'     = @{ shot = 's21-golden-orbit'; rec = 7; extra = "$lake -SailingLaunch=1 -SailingWeather=AfternoonBreeze -SailingWind=6 -SailingHour=16.85 -SailingDemo -SailingTWA=70 -SailingHoldTWA=70" }
	'R22-night'      = @{ shot = 's22-night-chase'; rec = 7; hud = $true; extra = "$lake -SailingLaunch=1 -SailingUiMode=natural -SailingWeather=CalmMorning -SailingWind=4 -SailingHour=21 -SailingEV=-4.5 -SailingDemo -SailingTWA=80 -SailingHoldTWA=80" }
	'H02-reach'      = @{ shot = 'h02-j22-reach-track'; rec = 6; extra = "$lake -SailingLaunch=1 -SailingWeather=AfternoonBreeze -SailingWind=10 -SailingHour=14 -SailingDemo -SailingTWA=90 -SailingHoldTWA=90" }
	'R03-briefing'   = @{ nopath = $true; rec = 8; interval = '0.0333333'; hud = $true; extra = "$lake -SailingDrill=LeavetheDock -SailingFrontEnd=Briefing -SailingHour=14" }
	'R08-career'     = @{ seedcopy = $true; nopath = $true; rec = 8; interval = '0.0333333'; hud = $true; extra = "$lake -SailingFrontEnd=Career -SailingHour=14 `"-SailingSave=D:\dev\ss-fix\Artifacts\bench\seed\run-profile.json`"" }
	'R08b-checkride' = @{ seedcopyready = $true; cleanlog = $true; nopath = $true; rec = 32; interval = '0.0333333'; hud = $true; timeout = 900; extra = "$lake -SailingFrontEnd=Career -SailingHour=14 `"-SailingSave=D:\dev\ss-fix\Artifacts\bench\seed\run-profile.json`" `"-SailingUIScript=Wait,Wait,Wait,WaitFor:Career,Tab,Tab,Tab,Tab,Tab,Tab,Tab,Tab,Tab,Tab,Tab,Tab,Enter,WaitFor:Quiz,Wait,Answer:all,Wait,Wait,Wait,Wait,Wait,Wait,Wait,Wait,Wait,Wait,Wait,Wait,Wait,Wait,Wait,Wait,Wait,Wait,Wait,Wait,Wait,Wait,Wait,Wait,Wait,Wait,Escape,Wait,WaitFor:Career,Escape,Wait,WaitFor:Title,Down,Down,Enter,Wait,Wait,Wait`"" }
	'R23-worldmap'   = @{ nopath = $true; rec = 8; interval = '0.0333333'; hud = $true; extra = "$lake -SailingFrontEnd=World -SailingHour=14" }
}
foreach ($name in $jobs.Keys) {
	if ($Only -and $name -notin $Only) { continue }
	$j = $jobs[$name]
	$shotName = if ($j.shot) { $j.shot } else { $name }
	$json = if ($j.shot) { $shots[$j.shot] } else { '{"frame":"boat","keys":[{"t":0,"orbit":[-120,20,2]}]}' }
	if (-not $json) { Note "$name SKIPPED: no shot file $($j.shot)"; continue }
	if ($j.seedcopyready) { Copy-Item "$B\seed\profile-daysailor-ready.json" "$B\seed\run-profile.json" -Force }   # every lesson at silver, the checkride not yet taken (throwaway)
	if ($j.seedcopy) { Copy-Item "$B\seed\profile-daysailor-certified.json" "$B\seed\run-profile.json" -Force }   # a throwaway copy each run, never Bean's profile
	if ($j.extra -notmatch 'ForceDebugViewModes') { $j.extra += ' -DPCVars=r.ForceDebugViewModes=1' }   # every take (coordinator, Nov 25)
	$args2 = @{ Name = $name; ShotFile = $shotName; ShotJson = $json; Record = $j.rec; Extra = $j.extra; PkgName = $P; ReelDir = $RD; ResX = $rx; ResY = $ry; Bench = 3 }
	if ($j.nopath) { $args2.NoPath = $true }; if ($j.hud) { $args2.Hud = $true }; if ($j.interval) { $args2.Interval = $j.interval }; if ($j.timeout) { $args2.Timeout = $j.timeout }; if ($j.warm) { $args2.Warmup = $j.warm }; if ($j.seed) { $args2.SeedProfile = $j.seed }
	# A clean logbook (coordinator, Nov 25): the package's own Saved\Logbook held aside, the four seeded Lake Ray Hubbard sails in its place, put back after.
	$pkgLog = "D:\dev\ss-fix\Packaged\$P\SailingSim\Saved\Logbook"; $logHold = $null
	if ($j.cleanlog) { if (Test-Path $pkgLog) { $logHold = "$pkgLog.reel-hold-$(Get-Date -Format HHmmss)"; Rename-Item $pkgLog (Split-Path $logHold -Leaf) }; New-Item -ItemType Directory -Force $pkgLog | Out-Null; Copy-Item "$B\seed\logbook-clean\*.json" $pkgLog }
	try { $runOut = & $r @args2; Note "$name : $($runOut -join ' | ')" } catch { Note "$name FAILED: $_" } finally { if ($j.cleanlog) { $keep = "D:\dev\reel\$RD\$name-logbook"; if (Test-Path $keep) { Remove-Item $keep -Recurse -Force }; Move-Item $pkgLog $keep; if ($logHold) { Rename-Item $logHold 'Logbook' }; Note "$name logbook: seeded book kept at $keep, package logbook restored $(Test-Path $pkgLog)" } }
	if ($name -eq 'P2-storm') {
		# P2: the full take as an mp4; the 300-frame WebP scrub from 70 s to 295 s of the take (frames 93..392 at 0.75 s), so the front (~205 s) is ~60% in.
		$fd = "D:\dev\reel\$RD\P2-storm\rec"
		& ffmpeg -hide_banner -loglevel error -y -framerate 30 -i "$fd\frame_%04d.png" -c:v libx264 -pix_fmt yuv420p -crf 18 "D:\dev\reel\$RD\P2-storm-full.mp4"
		& ffmpeg -hide_banner -loglevel error -y -framerate 30 -start_number 93 -i "$fd\frame_%04d.png" -frames:v 300 -vf scale=1920:-1 -c:v libwebp_anim -quality 80 -loop 0 "D:\dev\reel\$RD\P2-storm-scrub.webp"
		Note "P2 outputs: mp4 $(Test-Path "D:\dev\reel\$RD\P2-storm-full.mp4"), webp $(Test-Path "D:\dev\reel\$RD\P2-storm-scrub.webp") (window 70-295 s = frames 93-392)"
	}
}
Note 'SATURDAY DONE'
