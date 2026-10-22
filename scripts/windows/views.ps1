# The visual bench views, dot-sourced by bench-visual-win.ps1 and prescreen-stills.ps1.
# Keep in step with VIEWS in scripts/bench-visual.sh.
$Views = [ordered]@{
	"beam8" = "-SailingWorld=Lake -SailingLaunch=1 -SailingWeather=AfternoonBreeze -SailingHour=12 -SailingWind=8 -SailingTWA=90 -SailingHoldTWA=90 -SailingCamYaw=200 -SailingCamPitch=-10"
	"beat15" = "-SailingWorld=Lake -SailingLaunch=1 -SailingWeather=AfternoonBreeze -SailingHour=16 -SailingWind=15 -SailingTWA=45"
	"storm" = "-SailingWorld=Lake -SailingLaunch=1 -SailingWeather=Thunderstorm -SailingHour=16 -SailingWeatherTime=200 -SailingTWA=100 -SailingHoldTWA=100 -SailingCamYaw=200 -SailingCamPitch=-8"
	"marina" = "-SailingWorld=Lake -SailingLaunch=0 -SailingWeather=AfternoonBreeze -SailingHour=10 -SailingWind=6 -SailingCamYaw=150 -SailingCamPitch=-12 -SailingCamDist=40"
	"coast-day" = "-SailingWorld=1 -SailingLaunch=1 -SailingWeather=AfternoonBreeze -SailingWind=12 -SailingTWA=60 -SailingHoldTWA=60 -SailingHour=11 -SailingCamYaw=250 -SailingCamPitch=-10"
	"coast-night" = "-SailingDate=2026-10-22 -SailingWorld=1 -SailingLaunch=1 -SailingWeather=AfternoonBreeze -SailingWind=12 -SailingTWA=60 -SailingHoldTWA=60 -SailingHour=21 -SailingCamYaw=150 -SailingCamPitch=-6 -SailingCamDist=14"
	"gulf-sea" = "-SailingWorld=Gulf -SailingLaunch=2 -SailingWeather=AfternoonBreeze -SailingWind=12 -SailingTWA=60 -SailingHoldTWA=60 -SailingHour=11 -SailingCamYaw=200 -SailingCamPitch=-5 -SailingCamDist=22"
	"helm-eye" = "-SailingWorld=Lake -SailingLaunch=1 -SailingCapture=HelmEye -SailingWeather=AfternoonBreeze -SailingWind=12 -SailingHour=15 -SailingTWA=45 -SailingHoldTWA=45"
	"slip" = "-SailingWorld=Lake -SailingDrill=LeavetheDock -SailingWeather=AfternoonBreeze -SailingHour=10 -SailingWind=6 -SailingCamYaw=160 -SailingCamPitch=-14 -SailingCamDist=26"
	"bridge" = "-SailingWorld=Lake -SailingStartAt=7060,880,183 -SailingKeepStart -SailingWeather=AfternoonBreeze -SailingHour=11 -SailingWind=8 -SailingCamYaw=180 -SailingCamPitch=-4 -SailingCamDist=20"
	"crew" = "-SailingWorld=Lake -SailingLaunch=1 -SailingWeather=AfternoonBreeze -SailingHour=15 -SailingWind=10 -SailingTWA=60 -SailingHoldTWA=60 -SailingCamYaw=250 -SailingCamPitch=-6 -SailingCamDist=2.6 -SailingCamTarget=-1.6,0.8,0.9"
	"marina-night" = "-SailingDate=2026-10-22 -SailingWorld=Lake -SailingDrill=LeavetheDock -SailingWeather=AfternoonBreeze -SailingHour=21.5 -SailingWind=4 -SailingCamYaw=200 -SailingCamPitch=-10 -SailingCamDist=40"
	"far-coast" = "-SailingWorld=1 -SailingStartAt=-21700,26000,315 -SailingKeepStart -SailingWeather=AfternoonBreeze -SailingWind=10 -SailingTWA=60 -SailingHoldTWA=60 -SailingHour=11 -SailingCamYaw=0 -SailingCamPitch=-3 -SailingCamDist=14"
	"far-coast-night" = "-SailingDate=2026-10-22 -SailingWorld=1 -SailingStartAt=-21700,26000,315 -SailingKeepStart -SailingWeather=AfternoonBreeze -SailingWind=10 -SailingTWA=60 -SailingHoldTWA=60 -SailingHour=21 -SailingCamYaw=0 -SailingCamPitch=-3 -SailingCamDist=14"
	"marseille-port" = "-SailingWorld=Marseille -SailingLaunch=1 -SailingWeather=AfternoonBreeze -SailingWind=12 -SailingTWA=60 -SailingHoldTWA=60 -SailingHour=14 -SailingCamYaw=120 -SailingCamPitch=-8 -SailingCamDist=30"
	"stream-run" = "-SailingWorld=TexasCoast -SailingStartAt=-11068,16118,124 -SailingKeepStart -SailingRun=40,124 -SailingWeather=AfternoonBreeze -SailingWind=12 -SailingTWA=90 -SailingHoldTWA=90 -SailingHour=11 -SailingCamYaw=200 -SailingCamPitch=-8 -SailingCamDist=14"
}
