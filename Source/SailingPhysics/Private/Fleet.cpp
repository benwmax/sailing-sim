// The fleet: particulars for every boat beyond the J/22 (which is FBoatConfig's default), and each boat's
// reference polar. Sources for every number are in docs/phase-4/fleet-data.json; estimates are labeled there.
#include "BoatModel.h"
#include "PolarReference.h"

namespace Sailing
{
	namespace
	{
		FFoilDef Foil(EFoilRole Role, Vec3 Center, double Area, double Chord, double AspectRatio, double StallDeg, int Hull = 0)
		{
			FFoilDef F;
			F.Role = Role;
			F.Hull = Hull;
			F.Params.Center = Center;
			F.Params.Area = Area;
			F.Params.Chord = Chord;
			F.Params.EffectiveAspectRatio = AspectRatio;
			F.Params.StallAngleDeg = StallDeg;
			F.Params.ProfileDrag = 0.009;
			if (Role == EFoilRole::Rudder) { F.VentStartDeg = 30.0; F.VentEndDeg = 55.0; F.VentDepth = 0.8; }
			if (Role == EFoilRole::HullLateral) { F.VentDepth = 0.0; F.Params.ProfileDrag = 0.0; } // hull friction is counted already
			return F;
		}

		void SetMain(FBoatConfig& C, double FootZ, double HeadZ, double FootChord, double HeadChord, double Roach, double LuffX, double LuffXHead, double Area,
			double LiftSlope, double AspectRatio, double Camber)
		{
			C.MainFootZ = FootZ; C.MainHeadZ = HeadZ; C.MainFootChord = FootChord; C.MainHeadChord = HeadChord; C.MainRoach = Roach;
			C.MainLuffX = LuffX; C.MainLuffXHead = LuffXHead; C.MainArea = Area;
			C.BoomZ = FootZ;
			C.Main.NumStrips = 4;
			C.BuildMain(0);
			C.Main.LiftSlope = LiftSlope;
			C.Main.InducedAspectRatio = AspectRatio;
			C.Main.BaseCamber = Camber;
		}

		void SetSail(FSailGeometry& S, double FootZ, double HeadZ, double FootChord, double HeadChord, double LuffXFoot, double LuffXHead, double Area,
			double LiftSlope, double AspectRatio, double Camber)
		{
			BuildSail(S, 4, FootZ, HeadZ, FootChord, HeadChord, 0.0, LuffXFoot, LuffXHead, Area);
			if (Camber >= 0.18) { S.MaxLift = 1.3; S.ParasiteDrag = 0.30; } // spinnaker
			S.LiftSlope = LiftSlope;
			S.InducedAspectRatio = AspectRatio;
			S.BaseCamber = Camber;
		}

		// Residuary resistance per unit weight against Froude number.
		// Light, flat dinghies: about half a keelboat's wave drag through the hump, then flat once planing.
		const std::vector<std::pair<double, double>> kPlaningDinghy = { { 0.0, 0.0 }, { 0.1, 0.0003 }, { 0.2, 0.0015 }, { 0.3, 0.005 }, { 0.35, 0.009 },
			{ 0.4, 0.015 }, { 0.45, 0.023 }, { 0.5, 0.031 }, { 0.6, 0.040 }, { 0.7, 0.052 }, { 0.8, 0.064 }, { 1.0, 0.077 }, { 1.3, 0.082 } };
		// Slender beach-cat hulls: no hump to speak of, but spray and wave drag keep climbing once a hull flies.
		const std::vector<std::pair<double, double>> kSlenderCat = { { 0.0, 0.0 }, { 0.1, 0.0003 }, { 0.2, 0.002 }, { 0.3, 0.006 }, { 0.4, 0.012 },
			{ 0.5, 0.020 }, { 0.6, 0.027 }, { 0.8, 0.042 }, { 1.0, 0.056 }, { 1.4, 0.075 } };
		const std::vector<std::pair<double, double>> kCruisingCat = { { 0.0, 0.0 }, { 0.1, 0.0002 }, { 0.2, 0.0018 }, { 0.3, 0.006 }, { 0.35, 0.010 },
			{ 0.4, 0.016 }, { 0.45, 0.022 }, { 0.5, 0.026 }, { 0.6, 0.028 }, { 0.7, 0.027 }, { 0.8, 0.025 } };
		const std::vector<std::pair<double, double>> kTrimaran = { { 0.0, 0.0 }, { 0.1, 0.0003 }, { 0.2, 0.002 }, { 0.3, 0.007 }, { 0.4, 0.016 },
			{ 0.5, 0.026 }, { 0.6, 0.033 }, { 0.8, 0.045 }, { 1.0, 0.056 }, { 1.4, 0.070 } };
		const std::vector<std::pair<double, double>> kCruiser = { { 0.00, 0.0000 }, { 0.10, 0.0002 }, { 0.15, 0.0006 }, { 0.20, 0.0015 }, { 0.25, 0.0032 },
			{ 0.30, 0.0065 }, { 0.35, 0.0130 }, { 0.40, 0.0290 }, { 0.45, 0.0600 }, { 0.50, 0.0950 }, { 0.55, 0.1150 }, { 0.60, 0.1250 }, { 0.70, 0.1350 }, { 0.80, 0.1400 } };

		FBoatConfig Sunfish()
		{
			// LOA 13 ft 9 in, beam 4 ft 1 in, 120 lb hull, lateen rig 75 sq ft on a 10 ft mast. One sailor, hiking.
			FBoatConfig C;
			C.Type = EBoatType::Sunfish; C.TrimHeelLimitDeg = 8.0; C.TrimMaxEaseDeg = 60.0; C.Name = "Sunfish";
			C.HullRigMass = 70.0; C.HullRigCG = Vec3(-0.1, 0.0, 0.30);
			C.BallastMass = 0.0; C.BallastCG = Vec3();
			C.CrewMass = 75.0; C.CrewCG = Vec3(-0.9, 0.0, 0.40); C.CrewCount = 1;
			C.CrewSitOut = 0.50; C.CrewHikeOut = 0.45; C.CrewMoveSpeed = 2.5; C.RightingLever = 1.0;
			C.RadiiOfGyration = Vec3(0.55, 1.05, 1.05);
			FHullShape H;
			H.BowX = 2.10; H.SternX = -2.09; H.WaterlineMidX = -0.05; H.WaterlineHalfLength = 1.98;
			H.MaxHalfBeam = 0.62; H.MaxBeamX = -0.2; H.AftLength = 1.9; H.TransomBeamLoss = 0.10;
			H.SheerZ = 0.22; H.SheerRise = 0.06; H.SheerRiseFromX = 0.8; H.BilgePower = 9.0; H.BowOverhangSlope = 0.6; H.SternOverhangSlope = 0.3;
			H.PlaningLift = 0.010;
			C.Hulls = { H };
			C.LengthOverall = 4.19; C.WaterlineLength = 3.96; C.Beam = 1.24; C.WaterlineBeam = 1.1; C.Draft = 0.89;
			C.Residuary = kPlaningDinghy;
			C.WettedAreaCoef = 3.2; C.FormFactor = 1.15; C.HullLateralArea = 0.10; C.MunkAddedMass = 40.0; C.YawDampingLinear = 60.0; C.HeaveDamping = 900.0;
			C.Foils = { Foil(EFoilRole::Board, Vec3(0.55, 0.0, -0.45), 0.17, 0.24, 3.5, 14.0), Foil(EFoilRole::Rudder, Vec3(-2.15, 0.0, -0.30), 0.08, 0.216, 3.5, 14.0) };
			C.Foils[0].bRetractable = true;
			C.MaxRudderAngleDeg = 35.0; C.RudderStockToCP = 0.03; C.TillerLength = 0.8; C.HelmStiffness = 150.0;
			// Lateen: the sail hangs between the boom and the upper spar; the luff (upper spar) rakes far aft.
			C.MastX = 1.25; C.MastheadZ = 3.3; C.MastDiameter = 0.065;
			// The yard and boom are sealed aluminium tubes (about 5 cm by 4.5 m each): capsized, they and the sail lie on the
			// water and hold her on her side until the sailor rights her (or the mast fills and she turns turtle slowly).
			C.SparFloatLiters = 18.0;
			SetMain(C, 0.55, 4.3, 3.6, 0.25, 0.0, 1.9, -0.6, 6.97, 2.8, 2.0, 0.12);
			C.Jib.NumStrips = 0; C.Spinnaker.NumStrips = 0;
			C.MainMaxEaseDeg = 100.0; // unstayed: the boom can go past square, sailing by the lee C.TravelerRangeDeg = 3.0;
			C.RigWindageCdA = 0.15; C.HullWindageCdA = 0.45;
			C.ReefLuffFraction.clear();
			C.Engines.clear();
			return C;
		}

		FBoatConfig ILCA7()
		{
			// ILCA 7 (Laser standard rig): LOA 4.23 m, LWL 3.81 m, beam 1.37 m, 59 kg hull (79.5 kg rigged, no sail),
			// 7.06 m^2 una rig on an unstayed two-piece mast. One sailor, 82 kg ideal, hiking.
			FBoatConfig C;
			C.Type = EBoatType::ILCA7; C.TrimHeelLimitDeg = 8.0; C.TrimMaxEaseDeg = 60.0; C.Name = "ILCA 7 (Laser)";
			C.HullRigMass = 80.0; C.HullRigCG = Vec3(-0.05, 0.0, 0.42);
			C.BallastMass = 0.0; C.BallastCG = Vec3();
			C.CrewMass = 82.0; C.CrewCG = Vec3(-0.9, 0.0, 0.45); C.CrewCount = 1;
			C.CrewSitOut = 0.55; C.CrewHikeOut = 0.55; C.CrewMoveSpeed = 2.5; C.RightingLever = 1.1;
			C.RadiiOfGyration = Vec3(0.60, 1.10, 1.10);
			FHullShape H;
			H.BowX = 2.12; H.SternX = -2.11; H.WaterlineMidX = -0.12; H.WaterlineHalfLength = 1.905;
			H.MaxHalfBeam = 0.685; H.MaxBeamX = -0.3; H.AftLength = 1.8; H.TransomBeamLoss = 0.18;
			H.SheerZ = 0.30; H.SheerRise = 0.08; H.SheerRiseFromX = 0.8; H.BilgePower = 7.0; H.BowOverhangSlope = 0.8; H.SternOverhangSlope = 0.3;
			H.PlaningLift = 0.010;
			C.Hulls = { H };
			C.LengthOverall = 4.23; C.WaterlineLength = 3.81; C.Beam = 1.37; C.WaterlineBeam = 1.1; C.Draft = 0.79;
			C.Residuary = kPlaningDinghy;
			C.WettedAreaCoef = 2.75; C.HullLateralArea = 0.10; C.MunkAddedMass = 40.0; C.YawDampingLinear = 60.0;
			C.Foils = { Foil(EFoilRole::Board, Vec3(0.40, 0.0, -0.45), 0.24, 0.341, 4.0, 14.0), Foil(EFoilRole::Rudder, Vec3(-2.22, 0.0, -0.33), 0.10, 0.203, 4.0, 14.0) };
			C.Foils[0].bRetractable = true;
			C.MaxRudderAngleDeg = 35.0; C.RudderStockToCP = 0.03; C.TillerLength = 0.8; C.HelmStiffness = 150.0;
			C.MastX = 1.05; C.MastheadZ = 6.3; C.MastDiameter = 0.064;
			SetMain(C, 0.95, 6.0, 2.73, 0.30, 0.15, 1.02, 0.85, 7.06, 3.4, 3.8, 0.12);
			C.Jib.NumStrips = 0; C.Spinnaker.NumStrips = 0;
			C.MainMaxEaseDeg = 100.0; // unstayed: the boom can go past square, sailing by the lee C.TravelerRangeDeg = 4.0;
			C.RigWindageCdA = 0.15; C.HullWindageCdA = 0.5;
			C.ReefLuffFraction.clear();
			C.Engines.clear();
			return C;
		}

		FBoatConfig Catalina22()
		{
			// Catalina 22 swing keel: LOA 21 ft 6 in, LWL 19 ft 4 in, beam 7 ft 8 in, 2,250 lb, 550 lb cast-iron keel
			// (5 ft draft down, 2 ft up). Masthead sloop I 25.83, J 8, P 21, E 9.66 ft; 135% genoa; outboard.
			FBoatConfig C;
			C.Type = EBoatType::Catalina22; C.TrimHeelLimitDeg = 20.0; C.TrimMaxEaseDeg = 25.0; C.Name = "Catalina 22";
			C.HullRigMass = 771.0; C.HullRigCG = Vec3(-0.1, 0.0, 0.45);
			C.BallastMass = 250.0; C.BallastCG = Vec3(0.35, 0.0, -0.85);
			C.CrewMass = 227.0; C.CrewCG = Vec3(-1.4, 0.0, 0.65); C.CrewCount = 3;
			C.CrewSitOut = 0.40; C.CrewHikeOut = 0.45;
			C.RadiiOfGyration = Vec3(0.95, 1.70, 1.60);
			FHullShape H;
			H.BowX = 3.30; H.SternX = -3.25; H.WaterlineMidX = -0.05; H.WaterlineHalfLength = 2.946;
			H.MaxHalfBeam = 1.17; H.MaxBeamX = -0.3; H.AftLength = 2.9; H.TransomBeamLoss = 0.25;
			H.SheerZ = 0.72; H.SheerRise = 0.12; H.SheerRiseFromX = 0.8; H.BilgePower = 3.5;
			C.Hulls = { H };
			C.LengthOverall = 6.55; C.WaterlineLength = 5.89; C.Beam = 2.34; C.WaterlineBeam = 1.95; C.Draft = 1.52;
			C.Foils = { Foil(EFoilRole::Keel, Vec3(0.40, 0.0, -0.95), 0.60, 0.61, 3.0, 15.0), Foil(EFoilRole::Rudder, Vec3(-3.35, 0.0, -0.40), 0.25, 0.305, 3.0, 14.0) };
			C.Foils[0].bRetractable = true; // swing keel, cranked up for the trailer or shallows
			C.MunkAddedMass = 260.0; C.HelmStiffness = 600.0;
			C.MastX = 0.86; C.MastheadZ = 8.84; C.BoomZ = 1.45; C.MastDiameter = 0.09;
			SetMain(C, 1.45, 7.85, 2.94, 0.25, 0.08, 0.82, 0.82, 9.42, 3.6, 4.2, 0.12);
			SetSail(C.Jib, 0.85, 8.6, 3.3, 0.12, 3.20, 0.95, 12.9, 4.0, 4.4, 0.13); // 135% genoa
			SetSail(C.Spinnaker, 1.0, 8.4, 4.1, 1.0, 3.6, 2.6, 26.0, 2.6, 2.2, 0.20);
			// Short and beamy for its length: past hull speed the wave drag climbs faster than the Catalina 30's.
			C.Residuary = kCruiser;
			for (auto& Point : C.Residuary) if (Point.first >= 0.4) Point.second *= 1.2;
			C.JibMinAngleDeg = 10.0;
			C.ReefLuffFraction = { 0.80 };
			C.Engines.clear();
			FEngineDef E; E.Position = Vec3(-3.35, 0.40, -0.40); E.MaxThrustN = 650.0; E.PropSpeedKnots = 7.0; E.PropDiameter = 0.22;
			C.Engines.push_back(E);
			return C;
		}

		FBoatConfig Catalina30()
		{
			// Catalina 30 standard rig: LOA 29 ft 11 in, LWL 25 ft, beam 10 ft 10 in, 10,200 lb, 4,200 lb fin keel,
			// 5 ft 3 in draft. I 41, J 11.5, P 35, E 11.5 ft; sails as measured on ORC certificate US 3522 (main 22.6 m^2,
			// genoa 33.4 m^2, spinnaker 60.3 m^2); 21 hp diesel, wheel steering, two reefs.
			FBoatConfig C;
			C.Type = EBoatType::Catalina30; C.TrimHeelLimitDeg = 22.0; C.TrimMaxEaseDeg = 25.0; C.Name = "Catalina 30";
			C.HullRigMass = 2722.0; C.HullRigCG = Vec3(-0.3, 0.0, 0.55);
			C.BallastMass = 1905.0; C.BallastCG = Vec3(0.25, 0.0, -1.05);
			C.CrewMass = 400.0; C.CrewCG = Vec3(-2.3, 0.0, 1.05); C.CrewCount = 5;
			C.CrewSitOut = 0.9; C.CrewHikeOut = 0.4; C.CrewMoveSpeed = 1.2;
			C.RadiiOfGyration = Vec3(1.35, 2.40, 2.40);
			FHullShape H;
			H.BowX = 4.55; H.SternX = -4.57; H.WaterlineMidX = -0.2; H.WaterlineHalfLength = 3.81;
			H.MaxHalfBeam = 1.65; H.MaxBeamX = -0.6; H.AftLength = 3.8; H.TransomBeamLoss = 0.40;
			H.SheerZ = 1.05; H.SheerRise = 0.15; H.SheerRiseFromX = 1.5; H.BilgePower = 3.0;
			C.Hulls = { H };
			C.LengthOverall = 9.12; C.WaterlineLength = 7.62; C.Beam = 3.30; C.WaterlineBeam = 2.8; C.Draft = 1.60;
			C.Residuary = kCruiser;
			C.WettedAreaCoef = 2.9; C.HullLateralArea = 1.4; C.MunkAddedMass = 1200.0; C.YawDampingLinear = 2500.0; C.HeaveDamping = 1200.0;
			C.Foils = { Foil(EFoilRole::Keel, Vec3(0.30, 0.0, -1.05), 1.35, 1.22, 2.6, 15.0), Foil(EFoilRole::Rudder, Vec3(-2.9, 0.0, -0.80), 0.56, 0.457, 3.2, 15.0) };
			C.MaxRudderAngleDeg = 35.0; C.RudderStockToCP = 0.04; C.TillerLength = 0.4; C.HelmStiffness = 6000.0; C.RudderResponseTime = 0.25;
			C.MastX = 1.05; C.MastheadZ = 13.99; C.MastDiameter = 0.16;
			SetMain(C, 2.0, 12.67, 3.50, 0.45, 0.20, 1.0, 1.0, 22.57, 3.6, 4.6, 0.12); // ORC-measured main, with roach
			SetSail(C.Jib, 1.3, 13.2, 5.25, 0.15, 4.45, 1.15, 32.85, 4.0, 4.6, 0.13);
			SetSail(C.Spinnaker, 1.6, 13.2, 6.3, 1.4, 4.9, 3.7, 60.3, 2.6, 2.2, 0.20); // ORC-measured spinnaker
			C.JibMinAngleDeg = 10.0;
			C.RigWindageCdA = 2.0; C.HullWindageCdA = 3.0;
			C.ReefLuffFraction = { 0.82, 0.66 };
			C.Engines.clear();
			FEngineDef E; E.Position = Vec3(-2.3, 0.0, -0.80); E.MaxThrustN = 2100.0; E.PropSpeedKnots = 7.8; E.PropDiameter = 0.38; E.PropWalk = 0.10;
			C.Engines.push_back(E);
			return C;
		}

		FBoatConfig Hobie16()
		{
			// Hobie 16: LOA 16 ft 7 in, beam 7 ft 11 in, 320 lb rigged, no boards (the asymmetric hulls give the lift),
			// main 13.77 m^2 + jib 5.12 m^2 on a rotating 26 ft 6 in mast, two crew on double trapeze.
			FBoatConfig C;
			C.Type = EBoatType::Hobie16; C.AddedResistanceCoef = 4.0; C.AddedResistanceSpeedCap = 4.0; C.TrimHeelLimitDeg = 10.7; C.TrimMaxEaseDeg = 45.0; C.Name = "Hobie 16"; C.bMultihull = true;
			C.HullRigMass = 145.0; C.HullRigCG = Vec3(0.0, 0.0, 0.75);
			C.BallastMass = 0.0; C.BallastCG = Vec3();
			C.CrewMass = 150.0; C.CrewCG = Vec3(-0.7, 0.0, 0.60); C.CrewCount = 2;
			C.CrewSitOut = 1.05; C.CrewHikeOut = 1.30; C.CrewMoveSpeed = 2.0; C.bTrapeze = true; C.RightingLever = 1.0;
			C.RadiiOfGyration = Vec3(1.05, 1.40, 1.60);
			C.AddedMassRatio = Vec3(0.03, 0.4, 1.0);
			FHullShape H;
			H.BowX = 2.52; H.SternX = -2.52; H.WaterlineMidX = 0.0; H.WaterlineHalfLength = 2.31;
			H.MaxHalfBeam = 0.27; H.MaxBeamX = -0.2; H.AftLength = 2.3; H.TransomBeamLoss = 0.06;
			H.SheerZ = 0.45; H.SheerRise = 0.12; H.SheerRiseFromX = 1.0; H.BilgePower = 1.6; H.BowOverhangSlope = 0.4; H.SternOverhangSlope = 0.2;
			FHullShape Port = H, Stbd = H;
			Port.CenterY = -0.935; Stbd.CenterY = 0.935; // Graphics G3: outside of the hulls at the published 2.41 m beam (the hull flies
			// at a little more heel than at 2.54 m, so the trimmer's heel limit went from 10 to 10.7 degrees: still flies in 15 kn)
			C.Hulls = { Port, Stbd };
			C.LengthOverall = 5.04; C.WaterlineLength = 4.62; C.Beam = 2.41; C.WaterlineBeam = 0.3; C.Draft = 0.61;
			C.Residuary = kSlenderCat;
			C.WettedAreaCoef = 2.4; C.HullLateralArea = 0.06; C.MunkAddedMass = 30.0; C.YawDampingLinear = 150.0; C.HeaveDamping = 700.0;
			C.Foils = {
				Foil(EFoilRole::HullLateral, Vec3(0.1, -1.0, -0.08), 0.55, 3.6, 0.5, 22.0, 0), Foil(EFoilRole::HullLateral, Vec3(0.1, 1.0, -0.08), 0.55, 3.6, 0.5, 22.0, 1),
				Foil(EFoilRole::Rudder, Vec3(-2.62, -1.0, -0.30), 0.10, 0.20, 4.0, 14.0, 0), Foil(EFoilRole::Rudder, Vec3(-2.62, 1.0, -0.30), 0.10, 0.20, 4.0, 14.0, 1) };
			C.KeelDownwashFactor = 0.3;
			C.MaxRudderAngleDeg = 32.0; C.RudderStockToCP = 0.02; C.TillerLength = 1.0; C.HelmStiffness = 250.0;
			C.MastX = 0.55; C.MastheadZ = 8.5; C.MastDiameter = 0.09;
			// The sails sit above an open trampoline rather than a deck, so they lose the end-plate effect: lower
			// effective aspect ratios than the J/22's.
			SetMain(C, 0.75, 8.1, 2.60, 0.55, 0.28, 0.50, 0.50, 13.77, 3.9, 3.5, 0.11);
			SetSail(C.Jib, 0.65, 6.0, 2.0, 0.10, 2.35, 0.75, 5.12, 4.0, 3.0, 0.12);
			C.Spinnaker.NumStrips = 0;
			C.MainMaxEaseDeg = 70.0; C.TravelerRangeDeg = 22.0; C.JibMinAngleDeg = 9.0; C.JibMaxAngleDeg = 70.0;
			// Two crew out on the wire, trampoline, beams, bridles and a rotating mast: a lot of drag for 19 m^2 of sail.
			C.RigWindageCdA = 0.8; C.HullWindageCdA = 1.4;
			C.ReefLuffFraction.clear();
			C.Engines.clear();
			return C;
		}

		FBoatConfig Corsair880()
		{
			// Corsair 880 trimaran (standard rig): LOA 28 ft 8 in, beam 22 ft 3 in (8 ft 2 in folded), 3,659 lb empty,
			// daggerboard 1.6 m down / 0.43 m up, main about 33.5 m^2 + self-tacking jib about 18 m^2, asymmetric
			// spinnaker on the bowsprit, 9.9 hp outboard.
			FBoatConfig C;
			C.Type = EBoatType::Corsair880; C.AddedResistanceCoef = 3.0; C.AddedResistanceSpeedCap = 4.0; C.TrimHeelLimitDeg = 10.0; C.TrimMaxEaseDeg = 40.0; C.Name = "Corsair 880"; C.bMultihull = true;
			C.HullRigMass = 1760.0; C.HullRigCG = Vec3(-0.3, 0.0, 0.60);
			C.BallastMass = 0.0; C.BallastCG = Vec3();
			C.CrewMass = 240.0; C.CrewCG = Vec3(-2.6, 0.0, 0.95); C.CrewCount = 3;
			C.CrewSitOut = 1.5; C.CrewHikeOut = 1.0; C.CrewMoveSpeed = 1.5;
			C.RadiiOfGyration = Vec3(2.0, 2.4, 2.6);
			C.AddedMassRatio = Vec3(0.04, 0.5, 1.0);
			FHullShape Main;
			Main.BowX = 4.37; Main.SternX = -4.37; Main.WaterlineMidX = -0.1; Main.WaterlineHalfLength = 4.15;
			Main.MaxHalfBeam = 0.95; Main.MaxBeamX = -0.6; Main.AftLength = 3.7; Main.TransomBeamLoss = 0.25;
			Main.SheerZ = 1.0; Main.SheerRise = 0.15; Main.SheerRiseFromX = 1.5; Main.BilgePower = 2.2; Main.BowOverhangSlope = 0.6; Main.SternOverhangSlope = 0.3;
			FHullShape Ama;
			Ama.BowX = 3.9; Ama.SternX = -3.6; Ama.WaterlineMidX = 0.0; Ama.WaterlineHalfLength = 3.6;
			Ama.MaxHalfBeam = 0.55; Ama.MaxBeamX = -0.2; Ama.AftLength = 3.2; Ama.TransomBeamLoss = 0.25;
			Ama.SheerZ = 0.95; Ama.SheerRise = 0.1; Ama.BilgePower = 2.0; Ama.DepthScale = 1.6; Ama.DepthOffset = 0.68;
			FHullShape PortAma = Ama, StbdAma = Ama;
			PortAma.CenterY = -2.84; StbdAma.CenterY = 2.84; // Graphics G3: outside of the amas at the published 6.78 m beam
			C.Hulls = { Main, PortAma, StbdAma };
			C.LengthOverall = 8.74; C.WaterlineLength = 8.3; C.Beam = 6.78; C.WaterlineBeam = 1.4; C.Draft = 1.60;
			C.Residuary = kTrimaran;
			C.WettedAreaCoef = 2.45; C.HullLateralArea = 0.5; C.MunkAddedMass = 350.0; C.YawDampingLinear = 900.0;
			C.Foils = { Foil(EFoilRole::Board, Vec3(0.5, 0.0, -1.0), 0.35, 0.30, 5.0, 14.0), Foil(EFoilRole::Rudder, Vec3(-4.5, 0.0, -0.45), 0.25, 0.25, 4.0, 14.0) };
			C.Foils[0].bRetractable = true;
			C.MaxRudderAngleDeg = 32.0; C.RudderStockToCP = 0.03; C.TillerLength = 1.1; C.HelmStiffness = 500.0;
			C.MastX = 0.6; C.MastheadZ = 13.0; C.MastDiameter = 0.16;
			SetMain(C, 2.0, 12.6, 4.2, 1.2, 0.2, 0.55, 0.55, 33.5, 3.9, 4.0, 0.11);
			SetSail(C.Jib, 1.2, 11.0, 3.3, 0.12, 4.2, 0.9, 18.0, 4.0, 3.5, 0.12);
			SetSail(C.Spinnaker, 1.5, 12.2, 6.8, 1.3, 5.8, 3.6, 75.0, 2.8, 2.6, 0.18); // not published: 75-85 m^2 estimated
			C.bAsymmetricSpinnaker = true;
			C.MainMaxEaseDeg = 75.0; C.TravelerRangeDeg = 15.0;
			C.RigWindageCdA = 2.2; C.HullWindageCdA = 3.5; // beams, nets, three hulls, crew
			C.ReefLuffFraction = { 0.80, 0.62 };
			C.Engines.clear();
			FEngineDef E; E.Position = Vec3(-4.45, 0.0, -0.40); E.MaxThrustN = 1000.0; E.PropSpeedKnots = 8.5; E.PropDiameter = 0.24;
			C.Engines.push_back(E);
			return C;
		}

		FBoatConfig Lagoon42()
		{
			// Lagoon 42 (2016+): LOA 13.22 m, hull length 12.79 m, LWL about 12.5 m, beam 7.68 m, draft 1.26 m, 12.1 t
			// light (about 14 t sailing), square-top main 59 m^2 + self-tacking jib 35 m^2, Code 0 78 m^2, twin 45 hp
			// diesels on saildrives, wheel steering, three reefs.
			FBoatConfig C;
			C.Type = EBoatType::Lagoon42; C.TrimHeelLimitDeg = 4.0; C.TrimMaxEaseDeg = 35.0; C.Name = "Lagoon 42"; C.bMultihull = true;
			C.HullRigMass = 15180.0; C.HullRigCG = Vec3(-0.3, 0.0, 1.30); // 12.1 t light + water, fuel, dinghy, stores
			C.BallastMass = 0.0; C.BallastCG = Vec3();
			C.CrewMass = 320.0; C.CrewCG = Vec3(-3.5, 0.0, 2.2); C.CrewCount = 4;
			C.CrewSitOut = 0.0; C.CrewHikeOut = 0.0; C.CrewMoveSpeed = 1.0;
			C.RadiiOfGyration = Vec3(2.6, 3.5, 3.8);
			C.AddedMassRatio = Vec3(0.04, 0.5, 1.0);
			FHullShape H;
			H.BowX = 6.40; H.SternX = -6.39; H.WaterlineMidX = 0.0; H.WaterlineHalfLength = 6.25;
			H.MaxHalfBeam = 0.95; H.MaxBeamX = -0.8; H.AftLength = 5.5; H.TransomBeamLoss = 0.12;
			H.SheerZ = 1.55; H.SheerRise = 0.1; H.SheerRiseFromX = 3.0; H.BilgePower = 2.0; H.BowOverhangSlope = 0.3; H.SternOverhangSlope = 0.2;
			FHullShape Port = H, Stbd = H;
			Port.CenterY = -2.9; Stbd.CenterY = 2.9;
			C.Hulls = { Port, Stbd };
			C.LengthOverall = 13.22; C.Bowsprit = 0.43; C.WaterlineLength = 12.5; C.Beam = 7.68; C.WaterlineBeam = 1.3; C.Draft = 1.26; // LOA with the bowsprit (hulls 12.79 m)
			C.Residuary = kCruisingCat;
			C.WettedAreaCoef = 3.0; C.HullLateralArea = 2.0; C.MunkAddedMass = 4000.0; C.YawDampingLinear = 20000.0; C.HeaveDamping = 1500.0;
			C.Foils = {
				Foil(EFoilRole::Keel, Vec3(0.3, -2.9, -1.0), 2.2, 3.4, 0.9, 18.0, 0), Foil(EFoilRole::Keel, Vec3(0.3, 2.9, -1.0), 2.2, 3.4, 0.9, 18.0, 1),
				Foil(EFoilRole::Rudder, Vec3(-5.4, -2.9, -0.85), 0.5, 0.55, 3.0, 15.0, 0), Foil(EFoilRole::Rudder, Vec3(-5.4, 2.9, -0.85), 0.5, 0.55, 3.0, 15.0, 1) };
			C.MaxRudderAngleDeg = 35.0; C.RudderStockToCP = 0.05; C.TillerLength = 0.45; C.HelmStiffness = 40000.0; C.RudderResponseTime = 0.4;
			C.MastX = -0.4; C.MastheadZ = 20.6; C.MastDiameter = 0.25;
			// Cruising Dacron, sheeted from a fixed traveler: less lift for the area than a racing rig.
			SetMain(C, 3.2, 20.2, 5.8, 1.8, 0.12, -0.45, -0.45, 59.0, 3.3, 4.0, 0.12);
			SetSail(C.Jib, 2.4, 17.8, 4.3, 0.15, 4.0, -0.2, 35.0, 3.5, 3.8, 0.13);
			SetSail(C.Spinnaker, 2.4, 19.5, 7.2, 0.4, 6.4, -0.1, 78.0, 3.2, 3.4, 0.12); // Code 0 on the bowsprit
			C.bAsymmetricSpinnaker = true;
			C.MainMaxEaseDeg = 65.0; C.TravelerRangeDeg = 12.0; C.JibMinAngleDeg = 6.0; C.JibMaxAngleDeg = 45.0; // self-tacking track
			C.RigWindageCdA = 6.0; C.HullWindageCdA = 24.0; // tall house front, flybridge and bimini, high topsides
			C.ReefLuffFraction = { 0.82, 0.66, 0.50 };
			C.Engines.clear();
			FEngineDef E; E.MaxThrustN = 4000.0; E.PropSpeedKnots = 10.5; E.PropDiameter = 0.43; E.PropWalk = 0.05;
			E.Position = Vec3(-3.3, -2.9, -1.0); E.Hull = 0; C.Engines.push_back(E);
			E.Position = Vec3(-3.3, 2.9, -1.0); E.Hull = 1; E.PropWalk = -0.05; C.Engines.push_back(E); // counter-rotating
			return C;
		}
	}

	FBoatConfig FBoatConfig::Make(EBoatType Type)
	{
		FBoatConfig C;
		switch (Type)
		{
		case EBoatType::Sunfish: C = Sunfish(); break;
		case EBoatType::ILCA7: C = ILCA7(); break;
		case EBoatType::Catalina22: C = Catalina22(); break;
		case EBoatType::Catalina30: C = Catalina30(); break;
		case EBoatType::Hobie16: C = Hobie16(); break;
		case EBoatType::Corsair880: C = Corsair880(); break;
		case EBoatType::Lagoon42: C = Lagoon42(); break;
		default: return C;
		}
		// The rest of the fleet starts from the J/22. Her helm balance (Phase 8: rudder downwash, heel-induced yaw and the
		// form factor that went with them) was calibrated on the J/22 alone, so a boat that does not set its own keeps
		// the earlier values.
		const FBoatConfig J22;
		if (C.KeelDownwashFactor == J22.KeelDownwashFactor) C.KeelDownwashFactor = 1.0;
		if (C.HeelYawCoef == J22.HeelYawCoef) C.HeelYawCoef = 0.0;
		if (C.FormFactor == J22.FormFactor) C.FormFactor = 1.10;
		return C;
	}

	namespace
	{
		using FTable = std::vector<std::vector<double>>; // rows: TWS; columns: speeds at the angles below

		// Dinghy reference points from measured racing speeds include surfing and crew kinetics (pumping, rocking),
		// which no steady VPP sails: Day (2017, section 6.1) finds even a validated Laser VPP "somewhat lower" than
		// the measured downwind data, a gap two extra knots of wind only partly closes. Points at 120 degrees and
		// deeper are scaled by this factor for the steady-state test.
		constexpr double kNoSurfing = 0.85;
		std::vector<double> NoSurf(std::vector<double> Row, const std::vector<double>& Angles)
		{
			for (size_t I = 0; I < Row.size(); ++I) if (Angles[I] >= 120.0) Row[I] *= kNoSurfing;
			return Row;
		}

		void AddTable(std::vector<FPolarPoint>& Out, const double* Tws, int NumTws, const std::vector<double>& Angles, const FTable& Speeds,
			const char* Note, double SpinFromTwa, double Tolerance = 0.10, double Scale = 1.0)
		{
			for (int W = 0; W < NumTws; ++W)
			{
				for (size_t A = 0; A < Angles.size(); ++A)
				{
					Out.push_back({ Tws[W], Angles[A], Speeds[W][A] * Scale, Note, Angles[A] >= SpinFromTwa, Tolerance });
				}
			}
		}
	}

	const std::vector<FPolarPoint>& FleetReferencePolar(EBoatType Type)
	{
		static std::vector<FPolarPoint> Polars[int(EBoatType::Count)];
		std::vector<FPolarPoint>& P = Polars[int(Type)];
		if (!P.empty()) return P;
		const double Tws[] = { 6.0, 10.0, 15.0 };
		const double Tws16[] = { 6.0, 10.0, 16.0 };
		switch (Type)
		{
		case EBoatType::J22:
		{
			P = J22ReferencePolar();
			// With the spinnaker: ORC's own downwind numbers (no non-spinnaker factor).
			const char* Orc = "ORC, spinnaker";
			const char* Interp = "ORC, spinnaker, 15 kn interpolated 14-20";
			for (const FPolarPoint& Q : std::vector<FPolarPoint>{
				{ 6, 110, 4.9, Orc, true }, { 6, 135, 4.2, Orc, true }, { 6, 150, 3.6, Orc, true },
				{ 10, 110, 6.2, Orc, true }, { 10, 135, 5.9, Orc, true }, { 10, 150, 5.4, Orc, true },
				{ 15, 110, 7.2 + 1.1 / 6, Interp, true }, { 15, 135, 6.8 + 2.4 / 6, Interp, true }, { 15, 150, 6.4 + 1.7 / 6, Interp, true } })
			{
				P.push_back(Q);
			}
			break;
		}
		case EBoatType::ILCA7:
		{
			const std::vector<double> A = { 45, 60, 90, 120, 150 };
			AddTable(P, Tws, 3, A, { NoSurf({ 3.4, 3.9, 4.3, 4.2, 3.6 }, A), NoSurf({ 4.7, 5.4, 6.2, 6.2, 5.1 }, A), NoSurf({ 5.2, 6.6, 9.0, 9.4, 8.2 }, A) },
				"estimate from measured racing speeds (PMC9719898) and Day 2017 VPP; x0.85 at 120+ (no surfing)", 999.0);
			// The measured data pins upwind and downwind VMG; the reaching speeds in between were judged (+/-15%).
			for (FPolarPoint& Q : P) if (Q.TrueWindAngleDeg > 50.0 && Q.TrueWindAngleDeg < 140.0) Q.Tolerance = 0.15;
			break;
		}
		case EBoatType::Sunfish:
		{
			const std::vector<double> A = { 48, 60, 90, 120, 150 };
			AddTable(P, Tws, 3, A, { NoSurf({ 3.11, 3.57, 3.93, 3.84, 3.29 }, A), NoSurf({ 4.3, 4.94, 5.67, 5.67, 4.66 }, A), NoSurf({ 4.76, 6.04, 8.23, 8.6, 7.5 }, A) },
				"estimate: ILCA 7 x Portsmouth 91.1/99.6; x0.85 at 120+ (no surfing)", 999.0, 0.15);
			break;
		}
		case EBoatType::Catalina22:
			AddTable(P, Tws16, 3, { 52, 60, 90, 120, 150 }, { { 4.03, 4.26, 4.32, 4.09, 3.23 }, { 5.19, 5.36, 5.52, 5.52, 4.81 }, { 5.56, 5.72, 5.99, 6.25, 5.89 } },
				"estimate: Catalina 30 ORC x PHRF 270/183", 110.0);
			break;
		case EBoatType::Catalina30:
			AddTable(P, Tws16, 3, { 52, 60, 90, 120, 150 }, { { 4.51, 4.76, 4.83, 4.57, 3.61 }, { 5.8, 5.99, 6.18, 6.17, 5.38 }, { 6.33, 6.51, 6.82, 7.11, 6.7 } },
				"ORC certificate US 3522 (standard rig)", 110.0);
			break;
		case EBoatType::Hobie16:
			// Only the 10 kn curve is published (Hobie Hotline, 1978, digitized; the article calls it optimistic and says it
			// does not scale to other winds). 6 kn is a scaled estimate; no 15 kn row: the fleet tests check behavior there.
			AddTable(P, Tws, 2, { 45, 60, 90, 120, 150 }, { { 4.5, 5.6, 7.4, 6.3, 4.0 }, { 7.0, 9.1, 12.0, 10.3, 6.4 } },
				"Hobie Hotline 1978 polar at 10 kn (digitized, optimistic); 6 kn scaled estimate", 999.0, 0.20);
			break;
		case EBoatType::Corsair880:
			AddTable(P, Tws, 3, { 45, 60, 90, 120, 150 }, { { 4.8, 6.2, 7.5, 7.2, 5.2 }, { 6.8, 8.5, 11.0, 10.5, 7.8 }, { 8.5, 10.5, 14.0, 14.0, 10.5 } },
				"estimate anchored on review speeds (Yachting Monthly, SAIL); screacher/gennaker from 90", 90.0, 0.20);
			break;
		case EBoatType::Lagoon42:
			AddTable(P, Tws16, 3, { 60, 90, 120, 150 }, { { 2.5, 3.1, 3.3, 2.4 }, { 4.1, 5.1, 5.7, 4.3 }, { 6.5, 7.1, 7.6, 6.7 } },
				"estimate: third-party cruising polar (sabado.pol) x1.10 for a clean boat, checked against reviews", 999.0, 0.20, 1.10);
			break;
		default:
			break;
		}
		return P;
	}
}
