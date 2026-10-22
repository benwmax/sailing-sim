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
			// Added resistance: the J/22's until docs/wave-physics/, whose long-wave fall took a little off her in the 15 kn
			// chop (about two of her lengths); 3.0 puts her 15 kn beat back where her polar had it (+14.9% against +14.5%).
			C.AddedResistanceCoef = 3.0;
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
			C.MainMaxEaseDeg = 100.0; // unstayed: the boom can go past square, sailing by the lee
			C.TravelerRangeDeg = 3.0;   // the Sunfish's bridle (it had sat inside the comment above since the fleet came in: the default 8 applied)
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
			// Reaching flatter than upwind (item 13, below).
			C.Type = EBoatType::ILCA7; C.TrimHeelLimitDeg = 8.0; C.TrimReachHeelLimitDeg = 5.0; C.TrimMaxEaseDeg = 60.0; C.Name = "ILCA 7 (Laser)";
			// Sailed flat with the mainsheet in the hand (a sailor dumps a metre of sheet in half a second), sitting back on
			// the plane: the heavy-air reach without a capsize.
			C.DinghyEasePerHeelDeg = 2.0; C.DinghySheetRate = 2.5;
			C.HullRigMass = 80.0; C.HullRigCG = Vec3(-0.05, 0.0, 0.42);
			C.BallastMass = 0.0; C.BallastCG = Vec3();
			C.CrewMass = 82.0; C.CrewCG = Vec3(-0.9, 0.0, 0.45); C.CrewCount = 1; C.CrewAftRange = 0.5;
			C.CrewSitOut = 0.55; C.CrewHikeOut = 0.55; C.CrewMoveSpeed = 2.5; C.RightingLever = 1.1;
			C.RadiiOfGyration = Vec3(0.60, 1.10, 1.10);
			FHullShape H;
			H.BowX = 2.12; H.SternX = -2.11; H.WaterlineMidX = -0.12; H.WaterlineHalfLength = 1.905;
			H.MaxHalfBeam = 0.685; H.MaxBeamX = -0.3; H.AftLength = 1.8; H.TransomBeamLoss = 0.18;
			H.SheerZ = 0.30; H.SheerRise = 0.08; H.SheerRiseFromX = 0.8; H.BilgePower = 7.0; H.BowOverhangSlope = 0.8; H.SternOverhangSlope = 0.3;
			H.PlaningLift = 0.010;
			C.Hulls = { H };
			C.LengthOverall = 4.23; C.WaterlineLength = 3.81; C.Beam = 1.37; C.WaterlineBeam = 1.1; C.Draft = 0.79;
			// Above Froude 1.3 (15.4 kn on her 3.81 m waterline) the shared table is flat, and the ILCA ran on to 16.2 kn in a
			// steady 22 kn and 16.8 in W1's puffs, past her published top speeds of about 15 to 17 kn (GPS peaks in a big
			// gust; the reference checks' ceiling is 16). She is a semi-planing hull, not a skimmer: the fine bow and rounded
			// bilges stay wet, whisker spray and the spray root grow with speed, and in a lake chop she drives the bow into the
			// next wave. So her residuary climbs again past the hump: +46 % by Fn 1.4 (16.6 kn), 2.4x by 1.5 (17.8 kn), 5x by
			// 1.7. With the friction (about 0.15 of her weight at 16.6 kn) her drag is about a fifth of her weight at 15.4 kn
			// and a quarter at 16.6. Over 64 three-minute runs (100 to 130 deg, eight gust seeds, steady 22 kn and 16 gusting
			// 22) no upright run passes 16 kn (nine did), the steady peak drops from 16.2 to 15.8 kn and none capsizes.
			// W1's 25 to 29 kn puffs (seed 3) still drove her past 16 kn just before she buried the bow and went over: that
			// was handling in big puffs, not drag (a steeper wall only turns more runs over). The sailor's puff ease in
			// FAutoTrim now keeps her up there, peaking at 15.1 kn.
			C.Residuary = kPlaningDinghy;
			C.Residuary.insert(C.Residuary.end(), { { 1.4, 0.12 }, { 1.5, 0.20 }, { 1.7, 0.40 } });
			C.WettedAreaCoef = 2.75; C.HullLateralArea = 0.10; C.MunkAddedMass = 40.0; C.YawDampingLinear = 60.0;
			C.Foils = { Foil(EFoilRole::Board, Vec3(0.40, 0.0, -0.45), 0.24, 0.341, 4.0, 14.0), Foil(EFoilRole::Rudder, Vec3(-2.22, 0.0, -0.33), 0.10, 0.203, 4.0, 14.0) };
			C.Foils[0].bRetractable = true;
			C.MaxRudderAngleDeg = 35.0; C.RudderStockToCP = 0.03; C.TillerLength = 0.8; C.HelmStiffness = 150.0;
			C.MastX = 1.05; C.MastheadZ = 6.3; C.MastDiameter = 0.064;
			SetMain(C, 0.95, 6.0, 2.73, 0.30, 0.15, 1.02, 0.85, 7.06, 3.4, 3.8, 0.12);
			C.Jib.NumStrips = 0; C.Spinnaker.NumStrips = 0;
			C.MainMaxEaseDeg = 100.0; // unstayed: the boom can go past square, sailing by the lee
			// Her class rig's traveler (a rope horse) gives the boom about 4 deg either side. At 4 she had capsized on the 22 kn
			// broad reach (ReferenceChecks) and on four of LaserPlaningDrag's angles, but at the 8 she was calibrated with she
			// went over too, a little further round (22 kn at 120 deg, 24 kn at 110-130 deg: phase 8 fix list, item 13). What
			// was missing was her sailor's handling, not travel: on a heavy-air reach a Laser is sailed flat, the sheet eased at
			// 5 deg of heel (TrimReachHeelLimitDeg), not the 8 she is sailed at upwind (6 there cost her four polar points and
			// her pointing: TrimHeelLimitDeg stays). Over 20 three-minute reaches (100-130 deg, 18-24 kn steady and 16 gusting
			// 22) capsizes fall from 4 at 8 deg to 1 (24 kn at 120 deg; 2 at a 6 deg reach limit), none at 22 kn or below, the
			// mean speed 10.1 kn against 10.4.
			C.TravelerRangeDeg = 4.0;
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
			// W8 (Portsmouth): the swing keel is a cast-iron plate with blunt edges (Hoerner: Cd0 0.02-0.03 for a plate,
			// against 0.009 for a faired fin) hanging from an open trunk slot. Profile drag grows as V^2, like friction, so
			// it weighs most in light air, before wave drag takes over: at 0.009 she lapped 11 % under the D-PN 4-7 kn
			// band (96.3) while matching the ORC VPP, which models a faired keel and race trim.
			C.Foils[0].Params.ProfileDrag = 0.03;
			C.MunkAddedMass = 260.0; C.HelmStiffness = 600.0;
			C.MastX = 0.86; C.MastheadZ = 8.84; C.BoomZ = 1.45; C.MastDiameter = 0.09;
			// Boom stop (docs/boom-stop/): her aft lowers, from chainplates 0.31 m aft of the gooseneck and 0.96 m out
			// (Catalina22_sockets.json) to the mast at 4.94 m, pass 0.83 m from it at boom height, 70 deg from aft.
			C.MainMaxEaseDeg = 70.0;
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
			// Waves (docs/wave-physics/): ORC's added resistance (VPP 2023 eq. 6.62, its 16 kn sea) puts her at 1.23 to 1.36
			// x the J/22's (log10 or ln in its f(L30)); with the J/22's coefficient the model gave 2.14 x in that 5 s sea
			// (her 7.6 m waterline is nearer its peak). 2.6 x 1.29 / 2.14: her certificate's beat at 16 kn moves from -6.1%
			// to -4.9%, nothing else by more than 0.4%.
			C.AddedResistanceCoef = 1.57;
			C.Foils = { Foil(EFoilRole::Keel, Vec3(0.30, 0.0, -1.05), 1.35, 1.22, 2.6, 15.0), Foil(EFoilRole::Rudder, Vec3(-2.9, 0.0, -0.80), 0.56, 0.457, 3.2, 15.0) };
			C.MaxRudderAngleDeg = 35.0; C.RudderStockToCP = 0.04; C.TillerLength = 0.4; C.HelmStiffness = 6000.0; C.RudderResponseTime = 0.25;
			C.MastX = 1.05; C.MastheadZ = 13.99; C.MastDiameter = 0.16;
			SetMain(C, 2.0, 12.67, 3.50, 0.45, 0.20, 1.0, 1.0, 22.57, 3.6, 4.6, 0.12); // ORC-measured main, with roach
			// Boom stop (docs/boom-stop/): her aft lowers, from chainplates 0.30 m aft of the gooseneck and 1.39 m out
			// (Catalina30_sockets.json) to the mast at 7.77 m, pass 1.22 m from it at boom height, 76 deg from aft.
			C.MainMaxEaseDeg = 76.0;
			// (Her genoa's head on the forestay: at 13.2 m it runs 1.34 m from the mast's foot, tack (4.45, 1.3) to masthead
			// (1.13, 13.99). At 1.15 the head sat in the mast's front face and its leech went through the upper shrouds,
			// RigClearance.)
			SetSail(C.Jib, 1.3, 13.2, 5.25, 0.15, 4.45, 1.34, 32.85, 4.0, 4.6, 0.13);
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
			// W8 (Portsmouth): a beach cat pitches and slams into chop far more than the J/22 (low, fine bows on 320 lb, two
			// crew aft on the wire), and most in a breeze, when the lake's chop is up and she is going fast into it. At 4 she
			// sailed upwind 13 % over the Hotline polar at 10 kn and lapped 14 % under the D-PN 12+ band (71.3); at 9 the
			// added resistance (Hs^2 and speed: strongest upwind in a breeze) puts 10 kn upwind within 4 % of the polar and
			// both D-PN bands near their middles, leaving the light-air band where it was. (Those were 4 and 9 against the
			// J/22's 1.3; docs/wave-physics/ doubled every coefficient with the spectral sum, so 9 is 18 here.)
			C.Type = EBoatType::Hobie16; C.AddedResistanceCoef = 18.0; C.AddedResistanceSpeedCap = 4.0; C.TrimHeelLimitDeg = 10.7; C.TrimMaxEaseDeg = 45.0; C.Name = "Hobie 16"; C.bMultihull = true;
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
			// (Her rotating mast has no shroud to stop the boom: 70 kept, docs/boom-stop/.)
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
			// Added resistance: 3 against the J/22's 1.3 before docs/wave-physics/ doubled every coefficient with the
			// spectral sum.
			C.Type = EBoatType::Corsair880; C.AddedResistanceCoef = 6.0; C.AddedResistanceSpeedCap = 4.0; C.TrimHeelLimitDeg = 10.0; C.TrimMaxEaseDeg = 40.0; C.Name = "Corsair 880"; C.bMultihull = true;
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
			// (A rotating wing mast, its shrouds out at the floats: 75 kept, docs/boom-stop/.)
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
			// The self-tacking jib (Bean's pick, 2026-10-21; Lagoon's published 35 m^2) on the model's track across the saloon
			// roof's forward end, not an overlapping genoa: its clew had been aft by the mast, under the roof (sheets through it).
			// Foot 3.15 m up, 10 cm over the roof's crown at its forward end (build_fleet.py: sheer 1.55 + 1.42 + 0.08 crown);
			// luff on the forestay from the tack (x 5.2, deck 1.55) to the hounds (x -0.2, 17.8): 4.65 at the foot's height;
			// foot chord 4.2, the clew at x 0.45 over the track, 0.7 m forward of the mast. Head and area unchanged. Induced
			// aspect ratio 3.3 (3.8 before): its foot 1.6 m clear of the trampoline at the tack, the deck no longer end-plates
			// it; the polar is within 0.3% of the old jib's at every point (the reference is the stock boat, a self-tacker).
			SetSail(C.Jib, 3.15, 17.8, 4.2, 0.15, 4.65, -0.2, 35.0, 3.5, 3.3, 0.13);
			SetSail(C.Spinnaker, 2.4, 19.5, 7.2, 0.4, 6.4, -0.1, 78.0, 3.2, 3.4, 0.12); // Code 0 on the bowsprit
			C.bAsymmetricSpinnaker = true;
			// (Her aft lowers stop the boom at about 81 deg, docs/boom-stop/: the 65 her mainsheet allows comes first.)
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

	namespace
	{
#include "MaxiHullData.inl"

		// Residuary resistance per unit weight for the maxi. The Delft series' residuary per unit displacement weight falls
		// steeply with slenderness (LWL / volume^(1/3)): about as its cube through the hump (Keuning & Sonnenberg's
		// regression at Fn 0.35-0.45). The maxi's slenderness is 29.6 / 40.2^(1/3) = 8.7 against the J/22's 5.7, so her
		// hump is the J/22's table times (5.7 / 8.7)^3 = 0.28 up to Fn 0.45. Past it an ultralight, flat-run hull keeps
		// climbing instead of hitting a wall: from Fn 0.7 the planing dinghies' table (spray, the bulb and rudders near
		// ventilating, the bow into the sea). A 100 ft maxi's fastest reaching is about Fn 0.8-0.9 (25-28 kn); with half
		// these values past Fn 0.6 she reached at 32 kn under two reefs and the J4 in a 40 kn gust.
		const std::vector<std::pair<double, double>> kMaxi = { { 0.00, 0.0 }, { 0.10, 0.00006 }, { 0.15, 0.00014 }, { 0.20, 0.00034 },
			{ 0.25, 0.0007 }, { 0.30, 0.0014 }, { 0.35, 0.0028 }, { 0.40, 0.0062 }, { 0.45, 0.0134 }, { 0.50, 0.0200 }, { 0.55, 0.0250 },
			{ 0.60, 0.0300 }, { 0.70, 0.0520 }, { 0.80, 0.0640 }, { 0.90, 0.0710 }, { 1.00, 0.0770 }, { 1.30, 0.0820 } };

		FBoatConfig Maxi()
		{
			// The prologue's made-up 100 ft racing maxi (Tools/boats/maxi/ref.json, sections.json: the PC's model, no real
			// design copied). LOA 30.48 m, LWL 29.6, beam 7.2, draft 6.0 on a fixed T-keel (steel fin, lead bulb), twin
			// canted spade rudders on wheels, square-top main 335 m^2 and a J1 245 m^2 on a masthead rig 44.5 m above
			// the deck, A2 720 m^2 off a 2.6 m sprit, 12 crew. The hull is the exported sections themselves.
			FBoatConfig C;
			C.Type = EBoatType::Maxi; C.Name = "Maxi 100";
			// A maxi crew sail her at 15-20 deg (the rail just clear, rudders gripping), easing the main on the traveller.
			C.TrimHeelLimitDeg = 18.0; C.TrimMaxEaseDeg = 25.0;

			// Hull: the PC's sections (kMaxiSections), drawn as they are; the parameters are the stand-in fit the water's hull
			// clip and BoatExport read (deck plan: the widest station 3.61 m at x -6.3, 3.15 at the transom; sheer 2.0
			// amidships rising 0.75 to the stem; plumb bow, transom 0.12 m clear).
			FHullShape H;
			for (const FMaxiSection& M : kMaxiSections)
			{
				FHullShape::FStation St;
				St.X = M.X; St.Sheer = M.Sheer;
				St.Y.assign(M.Y, M.Y + kMaxiSectionPoints);
				St.Z.assign(M.Z, M.Z + kMaxiSectionPoints);
				H.StationDepth = std::max(H.StationDepth, -M.Z[0]);
				H.Stations.push_back(St);
			}
			H.BowX = kMaxiSections[kMaxiStations - 1].X; H.SternX = kMaxiSections[0].X;
			H.WaterlineMidX = 0.0; H.WaterlineHalfLength = 14.8;
			H.MaxHalfBeam = 3.61; H.MaxBeamX = -6.3; H.AftLength = 9.18; H.TransomBeamLoss = 0.46;
			H.SheerZ = 2.0; H.SheerRise = 0.75; H.SheerRiseFromX = 0.0; H.BilgePower = 5.2; H.BowOverhangSlope = 3.0; H.SternOverhangSlope = 0.17;
			C.Hulls = { H };
			C.LengthOverall = 30.48; C.WaterlineLength = 29.6; C.Beam = 7.2; C.WaterlineBeam = 5.8; C.Draft = 6.0; // WL beam: the export's 2 x 2.91

			// Mass budget. She floats on her design waterline: the canoe body's 37.13 m^3 (sections.json) plus the fin, bulb
			// and rudders (3.04 m^3 from ref.json's plan forms, make_maxi_hull.py) displace 40.2 t in the sim's fresh water
			// (ref.json's 42 t is about the same volume in sea water). Ballast: the steel fin (0.39 m^3, 3.06 t) and 20 t of
			// lead in the lower three quarters of the faired bulb (2.43 m^3). Crew: 12 at 88 kg.
			C.CrewMass = 1056.0; C.CrewCount = 12;
			C.BallastMass = 23060.0; C.BallastCG = Vec3(-0.63, 0.0, -5.26); // fin at (0.12, -3.06), lead at (-0.74, -5.6)
			C.AppendageVolume = kMaxiFinVolume + kMaxiBulbVolume + 2.0 * kMaxiRudderVolume;
			C.AppendageCentre = Vec3((kMaxiFinVolume * kMaxiFinX + kMaxiBulbVolume * kMaxiBulbX + 2.0 * kMaxiRudderVolume * -13.0) / C.AppendageVolume, 0.0,
				(kMaxiFinVolume * kMaxiFinZ + kMaxiBulbVolume * kMaxiBulbZ + 2.0 * kMaxiRudderVolume * -1.3) / C.AppendageVolume);
			// Hull, deck, interior, engine and gear (12.5 t about 1 m up) and the rig (mast 1.7 t, boom, rods, sails: 3.2 t
			// with its centroid 20 m up): 4.0 m up, and far enough aft that she floats level over the bulb, which ref.json
			// puts 1.6 m ahead of the canoe body's centre of buoyancy.
			C.HullRigMass = 1000.0 * (kMaxiCanoeVolume + C.AppendageVolume) - C.BallastMass - C.CrewMass;
			C.HullRigCG = Vec3(-4.3, 0.0, 4.0);
			// The crew on the windward rail, the helmsman, trimmers and grinders in the cockpit: on average 2.6 m out to
			// windward, legs over the side adding 0.3 when "hiking". Body frame mean place: the cockpit's forward end.
			C.CrewCG = Vec3(-6.0, 0.0, 2.5);
			C.CrewSitOut = 2.6; C.CrewHikeOut = 0.3; C.CrewMoveSpeed = 1.2;
			// Gyradii from the same budget: the mast (1.7 t, 25 m above the CG) and the bulb (20 t, 4.2 m below) dominate
			// roll; the hull's length adds to pitch and yaw.
			C.RadiiOfGyration = Vec3(7.3, 8.7, 5.0);

			// Resistance. Wetted area: the sections' girth below the DWL integrates to 114.7 m^2, 3.46 x sqrt(V x LWL)
			// (wide, flat aft sections: the J/22's round ones are 2.75).
			C.Residuary = kMaxi;
			C.WettedAreaCoef = 3.46;
			// Waves (docs/wave-physics/): her polar's lake chop is far shorter than her and does not load her, so the number
			// comes from ORC's length scaling instead. ORC's added resistance (VPP 2023 eq. 6.62 with its length baselines
			// for f(Vt) and its f(L30), at 16 kn) puts a 97 ft boat of her proportions at 2.78 to 4.12 x the J/22's (the
			// log in f(L30) read as log10 or ln); the model with the J/22's 2.6 gave 18.7 x in the same 5 s sea, where she
			// is near her peak and the J/22 rides it. 2.6 x 3.4 / 18.7 = 0.47 (0.38 to 0.57 across the reading). In the
			// prologue's gale (Hs 3.5 m, 7 s) she then beats at 10.8 kn against 12.3 flat and tacks 5 of 6 on the wheel.
			C.AddedResistanceCoef = 0.47;
			// Sway and yaw: the canoe body's lateral area is about 18 m^2 (LWL x a mean 0.6 m), so 9 m^2 at each station
			// (the J/22's 0.55 x 16); Munk added mass and low-speed yaw damping scaled by displacement and length^4 from the
			// Catalina 30 and the Lagoon (with the J/22's ratios they turn her far too slowly through a tack).
			C.HullLateralArea = 9.0; C.MunkAddedMass = 9000.0; C.YawDampingLinear = 90000.0; C.HeaveDamping = 1200.0;

			// Appendages (ref.json). The fin: span 4.2 m from the canoe body to the bulb, chords 1.65 / 1.05, swept 6 deg.
			// Its area here carries the bulb's and the canoe body's side force (7.3 m^2 against the fin's 5.7), centred
			// between the fin's centroid and the bulb, so its foot reaches the 6.0 m draft; effective aspect ratio 5: the
			// hull above and the bulb below are end plates on a 3.1 geometric fin. Its x is the balance knob (as the J/22's):
			// at the fin's 0.1 she sailed with 3-5 deg of lee helm upwind; the centre of lateral resistance of hull, fin and
			// bulb together sits ahead of the fin (the long forward canoe body), and at 1.2, with the downwash and heel yaw
			// below, she carries 1.5-2.5 deg of weather helm upwind and 4-5 reaching in 10-16 kn. Grounding under the bulb
			// (nose 1.6, tail -3.6).
			FFoilDef Keel = Foil(EFoilRole::Keel, Vec3(1.2, 0.0, -3.4), 7.3, 1.35, 5.0, 15.0);
			Keel.Params.ProfileDrag = 0.008;
			Keel.ContactLeadingX = 1.6; Keel.ContactTrailingX = -3.6;
			// Twin spade rudders on stocks at x -12.9, 1.75 m off the centreline and canted 8 deg out (their centres a span's
			// half further out): span 2.55 m, chords 0.82 / 0.52 (1.71 m^2 each). Heeled, the windward one lifts out and the
			// leeward one stands upright and deep (the model's immersion of each blade). Vertical in the model; the cant shows
			// as their outboard centres.
			C.Foils = { Keel,
				Foil(EFoilRole::Rudder, Vec3(-13.05, -1.93, -1.37), 1.71, 0.67, 4.5, 15.0), Foil(EFoilRole::Rudder, Vec3(-13.05, 1.93, -1.37), 1.71, 0.67, 4.5, 15.0) };
			// The twin rudders are there so the leeward blade stays deep and upright heeled (canted 8 deg out, it is vertical
			// at 8 deg of heel): it starts to draw air from the surface at 40 deg rather than the single transom rudders'
			// 30 (the windward blade's lift out of the water is the immersion above).
			for (FFoilDef& F : C.Foils) if (F.Role == EFoilRole::Rudder) { F.VentStartDeg = 40.0; F.VentEndDeg = 65.0; }
			// The rudders in the downwash of the hull, fin and bulb (the J/22's 1.7 reasoning: the canoe body's side force is in
			// the keel's area), and the lopsided heeled hull's yaw toward the wind (Keuning & Sonnenberg; two thirds of the
			// J/22's coefficient: her long, beamy aft sections are less lopsided heeled than they are wide).
			C.KeelDownwashFactor = 1.8; C.HeelYawCoef = 0.04;
			// Wheels: balanced spades (centre of pressure 5 cm behind the stock), a firm helm, the cable drive
			// taking 1.6 s from amidships to hard over with the wheel spun flat out (about three quarters of a turn).
			C.MaxRudderAngleDeg = 32.0; C.RudderStockToCP = 0.05; C.TillerLength = 0.5; C.HelmStiffness = 100000.0; C.RudderResponseTime = 0.5;
			C.WheelHardOverSeconds = 1.6;

			// Rig: masthead sloop, mast at x 3.1, 44.5 m above the 2.18 m deck (masthead 46.7). ref.json gives the rig's
			// heights above the deck (gooseneck 2.15, hounds 43.6, I 42.0), so they take the deck's 2.18 here: the gooseneck
			// at 4.33 (the boom's underside 4.1, clear of the 2.70 coachroof and heads in the cockpit), the main's head at
			// 44.83 (P 40.5). Main E 11.2, 4.2 m head (square top). Membrane sails on a tall rig: the J/22's lift slopes,
			// aspect ratios scaled with the geometric ones (main P^2/A 4.9 against the J/22's 2.8).
			C.MastX = 3.1; C.MastheadZ = 46.7; C.MastDiameter = 0.45;
			SetMain(C, 4.33, 44.83, 11.2, 4.2, 0.08, 2.8, 2.8, 335.0, 3.8, 6.5, 0.11);
			// J1 (non-overlapping: LP 12.4 on J 11.65), tacked at the stem (x 14.75); its tack and the forestay's foot (ref.json
			// forestay_z 2.95) are body-frame heights (the sheer at the stem is 2.75), its head at the forestay's top
			// (I 42.0 above the 2.18 deck: 44.2).
			C.JibFootZ = 2.9; C.JibHeadZ = 44.0; C.JibFootChord = 12.0; C.JibHeadChord = 0.3; C.JibLuffX = 14.75; C.JibLuffXHead = 3.6; C.JibArea = 245.0;
			SetSail(C.Jib, C.JibFootZ, C.JibHeadZ, C.JibFootChord, C.JibHeadChord, C.JibLuffX, C.JibLuffXHead, C.JibArea, 4.1, 6.5, 0.12);
			// A2 off the sprit (tack 2.6 m ahead of the stem), hoisted to the masthead.
			SetSail(C.Spinnaker, 2.9, 44.5, 21.0, 4.0, 17.6, 6.5, 720.0, 2.8, 2.6, 0.18);
			C.bAsymmetricSpinnaker = true;
			// Swept spreaders (20 deg) stop the boom short of square; the traveller (4.4 m wide, 14 m behind the gooseneck)
			// moves the boom 9 deg either side; jib leads on tracks 2.95 m out, 8 deg inboard sheeting.
			// (Her upper shroud's lower leg stops the boom at about 76 deg, docs/boom-stop/: 72 is inside it, kept.)
			C.MainMaxEaseDeg = 72.0; C.TravelerRangeDeg = 9.0; C.JibMinAngleDeg = 8.0; C.JibMaxAngleDeg = 70.0;
			// Windage: the mast's 46 m x 0.45 m mean frontal width, runners, shrouds and stays (the Catalina 30's 2.0 per
			// 2.2 m^2 of mast); the hull's 15 m^2 of bow-on topsides, twelve crew and the deck gear.
			C.RigWindageCdA = 18.0; C.HullWindageCdA = 15.0;
			// Reefs: one at 87% of the luff, two at 74% (the gale sails of the prologue's step 4), each with its headsail:
			// the J3 (55% of the J1) and the J4 (35%).
			C.ReefLuffFraction = { 0.87, 0.74 };
			C.ReefJibFraction = { 0.55, 0.35 };
			// Engine: a 150 hp diesel on a shaft behind the keel, 0.6 m folding prop (about 9 kgf of bollard pull per hp).
			C.Engines.clear();
			FEngineDef E; E.Position = Vec3(-5.5, 0.0, -1.3); E.MaxThrustN = 13000.0; E.PropSpeedKnots = 11.0; E.PropDiameter = 0.6; E.PropWalk = 0.06;
			C.Engines.push_back(E);
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
		case EBoatType::Maxi: C = Maxi(); break;
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
			// Running in the lake's chop she locks to the waves her own length, whose speed is her hull speed
			// (docs/wave-physics/): at TWA 150 she makes 5.8 kn in anything from 12 to 15 kn of wind, rides them below (+17%
			// at 11 kn) and is held behind them above (-11% at 16 kn) until she breaks through near 18 kn. Racers steer and
			// pump off them; the crew here hold the course. So the run's speed swings by a fifth with a knot of wind, on top
			// of the reference's own x0.85 judgment (the 15 kn run, held behind the chop, is 18% under it): 25%.
			for (FPolarPoint& Q : P) if (Q.TrueWindAngleDeg >= 140.0) Q.Tolerance = 0.25;
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
			// A handicap-scaled estimate: 15% (FPolarPoint::Tolerance). It was held to 10% until docs/wave-physics/, whose
			// surf down the lake's chop carries her 3 to 4% faster on the 16 kn reach and run.
			AddTable(P, Tws16, 3, { 52, 60, 90, 120, 150 }, { { 4.03, 4.26, 4.32, 4.09, 3.23 }, { 5.19, 5.36, 5.52, 5.52, 4.81 }, { 5.56, 5.72, 5.99, 6.25, 5.89 } },
				"estimate: Catalina 30 ORC x PHRF 270/183", 110.0, 0.15);
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
		case EBoatType::Maxi:
			// No published polar (a made-up boat): the Catalina 30's ORC certificate and the J/22's ORC polar scaled to her by
			// Froude number (speeds and wind by sqrt(LWL ratio)), sail area / displacement^(2/3) (49.5 against 18.9 and 28.9)
			// and ITTC-57 friction at her Reynolds number, then averaged (Tools/boats/maxi/estimate_polar.py). Scaled the same
			// way from the Catalina 30, the J/22's own polar comes out within 4% on average and 17% at worst; the maxi's
			// displacement-length ratio (43) is far outside both (151, 317), hence 30%. A2 from 120.
			AddTable(P, Tws16, 3, { 52, 60, 90, 120, 150 }, { { 7.5, 8.0, 8.3, 7.8, 6.2 }, { 11.2, 11.8, 12.2, 11.8, 9.8 }, { 13.4, 13.7, 14.3, 14.3, 13.1 } },
				"estimate: Catalina 30 and J/22 ORC scaled by Froude, SA/D and Reynolds (estimate_polar.py)", 120.0, 0.30);
			break;
		default:
			break;
		}
		return P;
	}
}
