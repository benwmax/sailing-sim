#include "BoatModel.h"
#include <utility>

namespace Sailing
{
	const char* BoatTypeName(EBoatType Type)
	{
		switch (Type)
		{
		case EBoatType::J22: return "J/22";
		case EBoatType::Sunfish: return "Sunfish";
		case EBoatType::ILCA7: return "ILCA 7 (Laser)";
		case EBoatType::Catalina22: return "Catalina 22";
		case EBoatType::Catalina30: return "Catalina 30";
		case EBoatType::Hobie16: return "Hobie 16";
		case EBoatType::Corsair880: return "Corsair 880";
		case EBoatType::Lagoon42: return "Lagoon 42";
		default: return "Boat";
		}
	}

	double FHullShape::DeckHalfBeam(double X) const
	{
		if (X > MaxBeamX)
		{
			const double U = (X - MaxBeamX) / (BowX - MaxBeamX + 0.02);
			return MaxHalfBeam * std::sqrt(std::max(0.0, 1.0 - U * U));
		}
		const double U = (MaxBeamX - X) / AftLength;
		return std::max(MaxHalfBeam - TransomBeamLoss * U * U, 0.02);
	}

	double FHullShape::SheerHeight(double X) const
	{
		return SheerZ + SheerRise * std::max(0.0, (X - SheerRiseFromX) / std::max(BowX - SheerRiseFromX, 1e-3));
	}

	double FHullShape::KeelLineDepth(double X, double MainDepth) const
	{
		const double D = MainDepth * DepthScale;
		const double U = (X - WaterlineMidX) / WaterlineHalfLength;
		if (std::fabs(U) <= 1.0)
		{
			return D * (1.0 - U * U) - DepthOffset;
		}
		return -(std::fabs(U) - 1.0) * WaterlineHalfLength * (U > 0.0 ? BowOverhangSlope : SternOverhangSlope) - DepthOffset;
	}

	double FHullShape::BottomZ(double X, double Y, double MainDepth) const
	{
		const double D = KeelLineDepth(X, MainDepth);
		const double B = std::max(DeckHalfBeam(X), 1e-3);
		const double R = std::min(std::fabs(Y) / B, 1.0);
		const double RP = BilgePower == 4.0 ? R * R * R * R : std::pow(R, BilgePower);
		return -D + (D + SheerHeight(X)) * RP;
	}

	void BuildSail(FSailGeometry& Sail, int NumStrips, double ZFoot, double ZHead, double FootChord, double HeadChord,
		double RoachFraction, double LuffXFoot, double LuffXHead, double TargetArea)
	{
		Sail.NumStrips = NumStrips;
		if (NumStrips <= 0) { Sail.TotalArea = 0.0; return; }
		const double DZ = (ZHead - ZFoot) / NumStrips;
		double Area = 0.0;
		for (int I = 0; I < NumStrips; ++I)
		{
			FSailStripGeometry& S = Sail.Strips[I];
			const double H = (I + 0.5) / NumStrips;
			S.ZBottom = ZFoot + DZ * I;
			S.ZTop = S.ZBottom + DZ;
			S.HeightFraction = H;
			S.LuffX = Lerp(LuffXFoot, LuffXHead, H);
			S.Chord = Lerp(FootChord, HeadChord, H) + RoachFraction * FootChord * std::sin(kPi * H);
			S.Area = S.Chord * DZ;
			Area += S.Area;
		}
		const double Scale = TargetArea / Area;
		for (int I = 0; I < NumStrips; ++I)
		{
			Sail.Strips[I].Chord *= Scale;
			Sail.Strips[I].Area *= Scale;
		}
		Sail.TotalArea = TargetArea;
	}

	void FBoatConfig::BuildMain(int Reefs)
	{
		const int N = int(ReefLuffFraction.size());
		const int R = Reefs < 0 ? 0 : (Reefs > N ? N : Reefs);
		const double F = R == 0 ? 1.0 : ReefLuffFraction[R - 1];
		// A reef lowers the sail: the head comes down, the new foot (the reef cringle) is a little shorter.
		const double HeadZ = MainFootZ + (MainHeadZ - MainFootZ) * F;
		const double FootChord = MainFootChord * (0.9 + 0.1 * F);
		const int Strips = Main.NumStrips > 0 ? Main.NumStrips : 4;
		BuildSail(Main, Strips, MainFootZ, HeadZ, FootChord, MainHeadChord, MainRoach, MainLuffX, Lerp(MainLuffX, MainLuffXHead, F), MainArea * std::pow(F, 1.3));
	}

	bool FBoatConfig::HasBoard() const
	{
		for (const FFoilDef& F : Foils) if (F.bRetractable) return true;
		return false;
	}

	FBoatConfig::FBoatConfig()
	{
		// J/22: LOA 22 ft 6 in, LWL 19 ft, beam 8 ft, 1,790 lb, 700 lb ballast. One hull, fin keel, transom rudder.
		Hulls.push_back(FHullShape());

		// Residuary resistance per unit weight against Froude number. Shape follows the Delft series for a
		// light-displacement keelboat; tuned against the J/22 polar.
		Residuary = { { 0.00, 0.0000 }, { 0.10, 0.0002 }, { 0.15, 0.0005 }, { 0.20, 0.0012 }, { 0.25, 0.0025 }, { 0.30, 0.0050 },
			{ 0.35, 0.0100 }, { 0.40, 0.0220 }, { 0.45, 0.0480 }, { 0.50, 0.0800 }, { 0.55, 0.1000 }, { 0.60, 0.1100 },
			// Past the hump a displacement keelboat's wave drag keeps climbing (Delft series); she is not a planing hull.
			// Flat here, she surfed to 12.5 kn in 20 kn of wind; the references are bursts of 9-12 kn and rare peaks near
			// her 16 kn record (Phase 8: J22-H-003, J22-S-001).
			{ 0.70, 0.1400 }, { 0.80, 0.1700 }, { 0.90, 0.2000 }, { 1.00, 0.2300 } };

		// Balance (Phase 8): the keel's side force includes the canoe body's (folded into its area below), so the rudder
		// sits in the downwash of the lower-aspect hull-and-keel system, more than a bare fin's: 1.7 x. With the
		// heel-induced yaw, she carries the weather helm the tuning guides describe: about 1 deg of rudder at 6 kn,
		// 1.5 at 10, 4-5 at 15 kn, growing as she heels.
		KeelDownwashFactor = 1.7;
		HeelYawCoef = 0.06;
		// J/22 crews keep her nearly flat upwind: traveler down, backstay on, ease in the puffs past about 13 deg
		// (North Sails and Quantum J/22 guides).
		TrimHeelLimitDeg = 13.0;
		// With the rudder now carrying its share of the side force (and its drag), the hull's form factor comes back to
		// the ITTC norm for a fair keelboat hull: the earlier 1.10 was standing in for that missing rudder drag.
		FormFactor = 1.04;

		// Fin keel, 3 ft 10 in draft. The canoe body's own side force is folded into the keel's area.
		FFoilDef Keel;
		Keel.Role = EFoilRole::Keel;
		Keel.Params.Center = Vec3(0.70, 0.0, -0.70); // swept fin, leading edge under the mast
		Keel.Params.Area = 0.95;
		Keel.Params.Chord = 0.80;
		Keel.Params.EffectiveAspectRatio = 3.0;
		Keel.Params.StallAngleDeg = 16.0;
		Keel.Params.ProfileDrag = 0.008;
		Keel.VentStartDeg = 60.0; Keel.VentEndDeg = 85.0; Keel.VentDepth = 0.9;
		Foils.push_back(Keel);

		// Transom-hung rudder.
		FFoilDef Rudder;
		Rudder.Role = EFoilRole::Rudder;
		Rudder.Params.Center = Vec3(-3.00, 0.0, -0.45);
		Rudder.Params.Area = 0.34;
		Rudder.Params.Chord = 0.36;
		Rudder.Params.EffectiveAspectRatio = 3.0;
		Rudder.Params.StallAngleDeg = 14.0;
		Rudder.Params.ProfileDrag = 0.008;
		Rudder.VentStartDeg = 30.0; Rudder.VentEndDeg = 55.0; Rudder.VentDepth = 0.8; // ventilation
		Foils.push_back(Rudder);

		// Fractional sloop: P 25.0 ft, E 9.75 ft, I 26.0 ft, J 8.0 ft. 223 sq ft (20.7 m^2) main + 100% jib.
		Main.NumStrips = 4;
		BuildMain(0);
		Main.LiftSlope = 3.65;
		Main.InducedAspectRatio = 4.5;
		Main.BaseCamber = 0.12;

		BuildSail(Jib, 4, 0.75, 8.25, 2.75, 0.12, 0.0, 3.40, 1.20, 9.2);
		Jib.LiftSlope = 4.1;
		Jib.InducedAspectRatio = 4.5;
		Jib.BaseCamber = 0.13;

		// Symmetric spinnaker on a pole, hoisted to the hounds: 30.94 m^2 as measured on the ORC one-design certificate
		// (Visual V3; the 16.3 m^2 used before was about half the real sail and left her slow downwind in a breeze).
		BuildSail(Spinnaker, 4, 0.9, 7.9, 5.2, 1.5, 0.0, 3.6, 2.6, 30.94);
		Spinnaker.LiftSlope = 2.6;
		Spinnaker.InducedAspectRatio = 2.2;
		Spinnaker.BaseCamber = 0.20;
		Spinnaker.MaxLift = 1.18; // with the full 30.94 m^2 (Visual V3): ORC 9.4 kn at 135 deg in 20 kn
		Spinnaker.ParasiteDrag = 0.30;

		ReefLuffFraction = { 0.82 };
		Draft = 1.16;

		// Most J/22s carry a small outboard on a transom bracket (4 hp is typical).
		FEngineDef Outboard;
		Outboard.Position = Vec3(-3.45, 0.35, -0.35);
		Outboard.MaxThrustN = 450.0;
		Outboard.PropSpeedKnots = 6.5;
		Outboard.PropDiameter = 0.20;
		Engines.push_back(Outboard);
	}

	FBoatModel::FBoatModel(const FBoatConfig& InConfig)
		: Config(InConfig)
	{
		Mass = Config.HullRigMass + Config.BallastMass + Config.CrewMass;
		CenterOfGravity = (Config.HullRigCG * Config.HullRigMass + Config.BallastCG * Config.BallastMass + Config.CrewCG * Config.CrewMass) / Mass;

		const Vec3& K = Config.RadiiOfGyration;
		Inertia = Vec3(Mass * K.X * K.X, Mass * K.Y * K.Y, Mass * K.Z * K.Z);
		EffectiveInertia = Inertia + Inertia.Mul(Config.AddedInertiaRatio);
		EffectiveMass = Vec3(Mass, Mass, Mass) + Config.AddedMassRatio * Mass;

		BuildHull();
		BuildContactPoints();
		Reset(0.0, 0.0, 0.0, 0.0);
	}

	namespace
	{
		constexpr int kStationsX = 26, kStationsY = 12;
	}

	double FBoatModel::SubmergedVolumeUpright(double Depth) const
	{
		double Volume = 0.0;
		for (const FHullShape& H : Config.Hulls)
		{
			const double DX = (H.BowX - H.SternX) / kStationsX;
			for (int I = 0; I < kStationsX; ++I)
			{
				const double X = H.SternX + DX * (I + 0.5);
				const double B = H.DeckHalfBeam(X);
				const double DY = 2.0 * B / kStationsY;
				for (int J = 0; J < kStationsY; ++J)
				{
					const double Y = -B + DY * (J + 0.5);
					Volume += std::max(0.0, -H.BottomZ(X, Y, Depth)) * DX * DY;
				}
			}
		}
		return Volume;
	}

	void FBoatModel::BuildHull()
	{
		// Find the canoe-body depth that floats the boat (with crew) at the design waterline.
		const double Target = Mass / kWaterDensity;
		double Lo = 0.02, Hi = 3.0;
		for (int I = 0; I < 60; ++I)
		{
			const double Mid = 0.5 * (Lo + Hi);
			(SubmergedVolumeUpright(Mid) < Target ? Lo : Hi) = Mid;
		}
		CanoeDepth = 0.5 * (Lo + Hi);

		Columns.clear();
		DesignHullVolume.assign(Config.Hulls.size(), 0.0);
		DesignVolume = 0.0;
		for (int HullIndex = 0; HullIndex < int(Config.Hulls.size()); ++HullIndex)
		{
			const FHullShape& H = Config.Hulls[HullIndex];
			const double DX = (H.BowX - H.SternX) / kStationsX;
			for (int I = 0; I < kStationsX; ++I)
			{
				const double X = H.SternX + DX * (I + 0.5);
				const double B = H.DeckHalfBeam(X);
				const double DY = 2.0 * B / kStationsY;
				for (int J = 0; J < kStationsY; ++J)
				{
					const double Y = -B + DY * (J + 0.5);
					const double ZB = H.BottomZ(X, Y, CanoeDepth);
					const double ZT = H.SheerHeight(X);
					if (ZT - ZB > 0.02)
					{
						Columns.push_back({ X, H.CenterY + Y, ZB, ZT, DX * DY, HullIndex });
						DesignHullVolume[HullIndex] += std::max(0.0, -ZB) * DX * DY;
					}
				}
			}
			DesignVolume += DesignHullVolume[HullIndex];
		}
	}

	Vec3 FBoatModel::DesignBuoyancyCentre() const
	{
		// The same columns the hydrostatics use, each cut at the design waterline (body Z = 0).
		double V = 0.0;
		Vec3 M;
		for (const FColumn& C : Columns)
		{
			if (C.ZBottom >= 0.0) continue;
			const double Vol = -C.ZBottom * C.Area;
			V += Vol;
			M += Vec3(C.X, C.Y, 0.5 * C.ZBottom) * Vol;
		}
		return V > 0.0 ? M * (1.0 / V) : Vec3();
	}

	void FBoatModel::BuildContactPoints()
	{
		BottomPoints.clear();
		OutlinePoints.clear();
		// Foil tips (leading and trailing edge) and points along each hull's keel line.
		for (const FFoilDef& F : Config.Foils)
		{
			if (F.Role == EFoilRole::HullLateral) continue;
			const double TipZ = std::max(F.Params.Center.Z - 0.5 * F.Span(), -Config.Draft);
			const double Half = 0.4 * F.Params.Chord;
			BottomPoints.push_back(Vec3(F.Params.Center.X + Half, F.Params.Center.Y, TipZ));
			BottomPoints.push_back(Vec3(F.Params.Center.X - Half, F.Params.Center.Y, TipZ));
		}
		for (const FHullShape& H : Config.Hulls)
		{
			for (double U : { 0.75, 0.0, -0.65 })
			{
				const double X = H.WaterlineMidX + U * H.WaterlineHalfLength;
				BottomPoints.push_back(Vec3(X, H.CenterY, -H.KeelLineDepth(X, CanoeDepth)));
			}
			// Deck edge at the rail: bow, three stations each side, the transom corners and middle.
			const double Len = H.BowX - H.SternX;
			OutlinePoints.push_back(Vec3(H.BowX - 0.05, H.CenterY, H.SheerHeight(H.BowX) - 0.2));
			for (double U : { 0.8, 0.55, 0.25 })
			{
				const double X = H.SternX + U * Len;
				const double B = 0.97 * H.DeckHalfBeam(X);
				OutlinePoints.push_back(Vec3(X, H.CenterY + B, H.SheerHeight(X) - 0.2));
				OutlinePoints.push_back(Vec3(X, H.CenterY - B, H.SheerHeight(X) - 0.2));
			}
			const double BT = 0.8 * H.DeckHalfBeam(H.SternX + 0.05);
			OutlinePoints.push_back(Vec3(H.SternX + 0.05, H.CenterY + BT, H.SheerZ - 0.2));
			OutlinePoints.push_back(Vec3(H.SternX + 0.05, H.CenterY - BT, H.SheerZ - 0.2));
			OutlinePoints.push_back(Vec3(H.SternX, H.CenterY, H.SheerZ - 0.2));
		}
		OutlinePoints.push_back(Vec3(Config.MastX, 0.0, Config.MastheadZ - 0.05));
	}

	std::vector<Vec3> FBoatModel::CleatPoints() const
	{
		// Bow cleat on the centerline (multihulls: the bows of the outer hulls), quarters and midship springs.
		std::vector<Vec3> Cleats;
		const FHullShape& Port = Config.Hulls.front();
		const FHullShape* Stbd = &Config.Hulls.front();
		const FHullShape* Left = &Port;
		for (const FHullShape& H : Config.Hulls)
		{
			if (H.CenterY > Stbd->CenterY) Stbd = &H;
			if (H.CenterY < Left->CenterY) Left = &H;
		}
		const double Z = Port.SheerZ - 0.1;
		if (Config.Hulls.size() == 1)
		{
			const FHullShape& H = Port;
			Cleats.push_back(Vec3(H.BowX - 0.25, 0.0, H.SheerHeight(H.BowX - 0.25)));
			const double BQ = 0.75 * H.DeckHalfBeam(H.SternX + 0.25);
			Cleats.push_back(Vec3(H.SternX + 0.25, BQ, Z));
			Cleats.push_back(Vec3(H.SternX + 0.25, -BQ, Z));
			const double BS = H.DeckHalfBeam(0.0);
			Cleats.push_back(Vec3(0.0, BS, Z));
			Cleats.push_back(Vec3(0.0, -BS, Z));
		}
		else
		{
			for (const FHullShape* H : { Left, Stbd })
			{
				const double Side = H->CenterY >= 0.0 ? 1.0 : -1.0;
				const double Out = H->CenterY + Side * 0.8 * H->MaxHalfBeam;
				Cleats.push_back(Vec3(H->BowX - 0.3, H->CenterY, H->SheerHeight(H->BowX - 0.3)));
				Cleats.push_back(Vec3(H->SternX + 0.3, Out, Z));
				Cleats.push_back(Vec3(0.0, Out, Z));
			}
		}
		return Cleats;
	}

	void FBoatModel::SetObstacles(const std::vector<FObstacleSegment>* InObstacles)
	{
		Obstacles = InObstacles;
		ObstacleBuckets.clear();
		ObstacleRows = ObstacleCols = 0;
		if (!Obstacles || Obstacles->empty()) return;
		double MinX = 1e30, MinY = 1e30, MaxX = -1e30, MaxY = -1e30;
		for (const FObstacleSegment& S : *Obstacles)
		{
			MinX = std::min({ MinX, S.AX - S.Radius, S.BX - S.Radius }); MaxX = std::max({ MaxX, S.AX + S.Radius, S.BX + S.Radius });
			MinY = std::min({ MinY, S.AY - S.Radius, S.BY - S.Radius }); MaxY = std::max({ MaxY, S.AY + S.Radius, S.BY + S.Radius });
		}
		const double Margin = 1.0; // hull points within contact distance (radius + 0.1 m) of a segment
		ObstacleX0 = MinX - Margin;
		ObstacleY0 = MinY - Margin;
		ObstacleRows = int((MaxX - ObstacleX0 + Margin) / ObstacleCell) + 1;
		ObstacleCols = int((MaxY - ObstacleY0 + Margin) / ObstacleCell) + 1;
		ObstacleBuckets.assign(size_t(ObstacleRows) * ObstacleCols, {});
		for (int I = 0; I < int(Obstacles->size()); ++I)
		{
			const FObstacleSegment& S = (*Obstacles)[I];
			const double Pad = S.Radius + Margin;
			const int R0 = int((std::min(S.AX, S.BX) - Pad - ObstacleX0) / ObstacleCell), R1 = int((std::max(S.AX, S.BX) + Pad - ObstacleX0) / ObstacleCell);
			const int C0 = int((std::min(S.AY, S.BY) - Pad - ObstacleY0) / ObstacleCell), C1 = int((std::max(S.AY, S.BY) + Pad - ObstacleY0) / ObstacleCell);
			for (int R = std::max(R0, 0); R <= std::min(R1, ObstacleRows - 1); ++R)
				for (int C = std::max(C0, 0); C <= std::min(C1, ObstacleCols - 1); ++C)
					ObstacleBuckets[size_t(R) * ObstacleCols + C].push_back(I);
		}
	}

	void FBoatModel::Reset(double X, double Y, double Heading, double Speed)
	{
		const int Reef = State.Reef;
		State = FBoatState();
		State.Reef = Reef;
		State.Orientation = Quat::FromAxisAngle(Vec3(0, 0, 1), Heading);
		State.Position = Vec3(X, Y, 0.0) + State.Orientation.Rotate(CenterOfGravity);
		State.Velocity = State.Orientation.Forward() * Speed;
		Telemetry = FBoatTelemetry();
		MainMeanLift = 0.0;
	}

	Vec3 FBoatModel::PointVelocityWorld(const Vec3& BodyPoint) const
	{
		const Vec3 R = State.Orientation.Rotate(BodyPoint - CenterOfGravity);
		const Vec3 OmegaWorld = State.Orientation.Rotate(State.AngularVelocity);
		return State.Velocity + OmegaWorld.Cross(R);
	}

	double FBoatModel::ResistanceCoefficient(double Froude) const
	{
		const auto& T = Config.Residuary;
		const int N = int(T.size());
		if (N == 0) return 0.0;
		if (Froude >= T[N - 1].first)
		{
			return T[N - 1].second;
		}
		for (int I = 1; I < N; ++I)
		{
			if (Froude < T[I].first)
			{
				const double U = (Froude - T[I - 1].first) / (T[I].first - T[I - 1].first);
				return Lerp(T[I - 1].second, T[I].second, U);
			}
		}
		return T[N - 1].second;
	}

	double FBoatModel::RightingMomentAt(double HeelRad) const
	{
		// Find the sinkage that supports the boat at this heel, then take the buoyancy moment about the CG.
		const Quat Q = Quat::FromAxisAngle(Vec3(1, 0, 0), HeelRad);
		auto Evaluate = [&](double Sink, double& OutVolume, double& OutMomentX)
		{
			OutVolume = 0.0;
			OutMomentX = 0.0;
			for (const FColumn& C : Columns)
			{
				const Vec3 Bottom = Q.Rotate(Vec3(C.X, C.Y, C.ZBottom) - CenterOfGravity) + Vec3(0, 0, CenterOfGravity.Z - Sink);
				const Vec3 Top = Q.Rotate(Vec3(C.X, C.Y, C.ZTop) - CenterOfGravity) + Vec3(0, 0, CenterOfGravity.Z - Sink);
				if (Bottom.Z >= 0.0 && Top.Z >= 0.0) continue;
				// Fraction of the column below the water, whichever end is down.
				const double F = Bottom.Z < Top.Z ? Clamp(-Bottom.Z / (Top.Z - Bottom.Z), 0.0, 1.0) : Clamp(-Top.Z / (Bottom.Z - Top.Z), 0.0, 1.0);
				const Vec3 Low = Bottom.Z < Top.Z ? Bottom : Top, High = Bottom.Z < Top.Z ? Top : Bottom;
				const double Vol = C.Area * (C.ZTop - C.ZBottom) * F;
				const Vec3 P = Low + (High - Low) * (0.5 * F) - Vec3(0, 0, CenterOfGravity.Z - Sink);
				OutVolume += Vol;
				OutMomentX += P.Y * Vol; // buoyancy up at lateral offset Y from the CG
			}
		};
		const double Target = Mass / kWaterDensity;
		double Lo = -3.0, Hi = 3.0, Vol = 0.0, MX = 0.0;
		for (int I = 0; I < 60; ++I)
		{
			const double Mid = 0.5 * (Lo + Hi);
			Evaluate(Mid, Vol, MX);
			(Vol < Target ? Lo : Hi) = Mid;
		}
		Evaluate(0.5 * (Lo + Hi), Vol, MX);
		// Buoyancy (up) at +Y produces a moment about +X of +Y * F (Y x Z = X). Positive heel lifts starboard,
		// so a righting moment is negative about X; report it as a positive number.
		return -MX * kWaterDensity * kGravity;
	}

	void FBoatModel::Step(double Dt, const FBoatControls& Controls, const FWindField& Wind, const FWaveField* Waves)
	{
		CurrentWaves = Waves;
		const FBoatConfig& C = Config;
		const Quat& Q = State.Orientation;
		const Vec3 Origin = OriginPosition();
		const Vec3 CGWorld = State.Position;
		const Vec3 OmegaWorld = Q.Rotate(State.AngularVelocity);
		const int NumHulls = int(C.Hulls.size());

		Vec3 ForceWorld(0.0, 0.0, -Mass * kGravity);
		Vec3 TorqueWorld;
		auto AddWorldForce = [&](const Vec3& F, const Vec3& PointWorld)
		{
			ForceWorld += F;
			TorqueWorld += (PointWorld - CGWorld).Cross(F);
		};
		Vec3 ForceBody, TorqueBody;
		auto AddBodyForce = [&](const Vec3& F, const Vec3& BodyPoint)
		{
			ForceBody += F;
			TorqueBody += (BodyPoint - CenterOfGravity).Cross(F);
		};
		auto WaterAt = [&](const Vec3& P) { return Waves ? Waves->Height(P.X, P.Y, State.Time) : 0.0; };

		// Hydrostatics and heave/roll/pitch damping: each hull column against the water surface.
		double HullVolume[8] = { 0, 0, 0, 0, 0, 0, 0, 0 };
		const Vec3 Axis = Q.Up();
		for (const FColumn& Col : Columns)
		{
			const Vec3 Base = Origin + Q.Rotate(Vec3(Col.X, Col.Y, Col.ZBottom));
			const double Len = Col.ZTop - Col.ZBottom;
			const Vec3 Tip = Base + Axis * Len;
			// The column's low end (the bottom when upright, the deck when inverted).
			const bool bUpright = Axis.Z >= 0.0;
			const Vec3 Low = bUpright ? Base : Tip;
			if (Low.Z >= 1.0) continue; // well clear of any lake chop
			double Water = 0.0, WaterVZ = 0.0, SlopeX = 0.0, SlopeY = 0.0;
			if (Waves)
			{
				Waves->Sample(Low.X, Low.Y, State.Time, Water, WaterVZ, SlopeX, SlopeY);
			}
			if (Low.Z >= Water) continue;
			const double Rise = std::max(std::fabs(Axis.Z) * Len, 1e-6);
			const double F = Clamp((Water - Low.Z) / Rise, 0.0, 1.0);
			const double Volume = Col.Area * Len * F;
			const Vec3 Dir = bUpright ? Axis : -Axis;
			const Vec3 Point = Low + Dir * (0.5 * F * Len);
			const Vec3 PointVel = State.Velocity + OmegaWorld.Cross(Point - CGWorld);
			const double Wet = std::min(1.0, F * Len / 0.1);
			const double Damping = -C.HeaveDamping * Col.Area * Wet * (PointVel.Z - WaterVZ);
			AddWorldForce(Vec3(0.0, 0.0, kWaterDensity * kGravity * Volume + Damping), Point);
			if (Col.Hull < 8) HullVolume[Col.Hull] += Volume;
		}

		// Crew: the CG assumes them on the centerline; moving them out (or onto the board) adds a gravity moment.
		{
			const Vec3 CrewWorld = Q.Rotate(Vec3(State.CrewOffsetX, State.CrewOffset, State.CrewOffsetZ));
			TorqueWorld += CrewWorld.Cross(Vec3(0.0, 0.0, -C.CrewMass * kGravity));
		}

		// Hull resistance per hull (ITTC-57 friction + residuary by Froude number), along the hull's motion.
		const double HeelAbs = std::fabs(Q.Heel());
		double MaxFroude = 0.0;
		for (int H = 0; H < NumHulls; ++H)
		{
			const FHullShape& Hull = C.Hulls[H];
			const double Vol = H < 8 ? HullVolume[H] : 0.0;
			if (Vol < 1e-5) continue;
			const double HullDepthHere = std::max(CanoeDepth * Hull.DepthScale - Hull.DepthOffset, 0.02);
			const Vec3 HullPoint(Hull.WaterlineMidX, Hull.CenterY, -0.5 * HullDepthHere);
			const Vec3 HullVel = Q.Unrotate(PointVelocityThroughWater(HullPoint));
			const double U = HullVel.X;
			const double V = std::fabs(U);
			const double Lwl = Hull.WaterlineLength();
			if (V > 1e-4)
			{
				// Planing: the flat run aft lifts the hull as it speeds up, so less of it is wet. The residuary table is
				// towing-tank style data that already includes the hull's dynamic lift, so wave drag is charged on the
				// whole weight this hull carries (buoyancy plus lift); the lift only shrinks the wetted area.
				const double Froude = V / std::sqrt(kGravity * Lwl);
				double Lift = 0.0;
				if (Hull.PlaningLift > 0.0 && U > 0.0)
				{
					const double Bottom = 0.7 * Lwl * 2.0 * Hull.MaxHalfBeam;
					Lift = 0.5 * kWaterDensity * V * V * Bottom * Hull.PlaningLift * SmoothStep(0.35, 0.9, Froude)
						* Clamp(Vol / std::max(DesignHullVolume[H], 1e-3), 0.0, 1.0) * std::max(0.0, std::cos(HeelAbs));
					AddWorldForce(Vec3(0.0, 0.0, Lift), Origin + Q.Rotate(Vec3(Hull.WaterlineMidX - 0.1 * Lwl, Hull.CenterY, 0.0)));
				}
				const double Wetted = C.WettedAreaCoef * std::sqrt(Vol * Lwl);
				const double Re = std::max(V * 0.7 * Lwl / kWaterViscosity, 1e4);
				const double LogRe = std::log10(Re) - 2.0;
				const double Cf = 0.075 / (LogRe * LogRe);
				const double Friction = 0.5 * kWaterDensity * V * V * Wetted * Cf * C.FormFactor * (1.0 + 0.4 * std::sin(HeelAbs));
				MaxFroude = std::max(MaxFroude, Froude);
				const double Carried = kWaterDensity * kGravity * Vol + Lift;
				const double Residuary = Carried * ResistanceCoefficient(Froude) * (1.0 + 2.0 * std::sin(HeelAbs) * std::sin(HeelAbs));
				// Added resistance in waves, from the actual sea state.
				double WaveResistance = 0.0;
				if (Waves)
				{
					// Summed over the sea's spectrum (Gerritsma-Beukelman shape): a hull pitches and heaves most, and so
					// loses most, in waves near her own length; chop much shorter than her barely moves her, and a
					// long swell she simply rides over. Into the waves the peak moves to longer waves as she goes faster
					// (she meets them more often, so a longer wave still matches her pitch period). Each band counts by
					// how far it comes from ahead.
					const Vec3 Fwd = Q.Forward();
					const double HullBeam = 2.0 * Hull.MaxHalfBeam;
					double Sum = 0.0;
					// The ocean's bins only as far as its mask lets the open sea in where she is (none in a bay).
					const std::vector<FWaveBand>& SeaBands = Waves->Bands();
					const size_t OceanFrom = Waves->OceanBandStart();
					const double OceanShare = OceanFrom < SeaBands.size() ? Waves->OceanShareAt(State.Position.X, State.Position.Y) : 0.0;
					for (size_t BandIndex = 0; BandIndex < SeaBands.size(); ++BandIndex)
					{
						const FWaveBand& Band = SeaBands[BandIndex];
						const double BandShare = BandIndex >= OceanFrom ? OceanShare : 1.0;
						const double IntoWaves = -(std::cos(Band.Direction) * Fwd.X + std::sin(Band.Direction) * Fwd.Y);
						const double Ratio = Band.Wavelength / Lwl;
						const double PeakEnd = 1.2 + 1.0 * Froude * std::max(IntoWaves, 0.0);
						const double R4 = Ratio * Ratio * Ratio * Ratio;
						double Response = R4 / (0.25 + R4);
						if (Ratio > PeakEnd) Response *= 1.0 / (1.0 + (Ratio - PeakEnd) * (Ratio - PeakEnd) / 0.64);
						// (Hs/2)^2 of a band is four times its variance.
						Sum += Response * 4.0 * Band.Variance * BandShare * (1.0 + IntoWaves) * (1.0 + IntoWaves) * 0.25;
					}
					WaveResistance = C.AddedResistanceCoef * kWaterDensity * kGravity * Sum * HullBeam * HullBeam / Lwl
						* Clamp(V / 2.0, 0.0, C.AddedResistanceSpeedCap) * Clamp(Vol / std::max(DesignHullVolume[H], 1e-3), 0.0, 1.0);
				}
				// Going astern, the transom leads: much more form drag than with the bow first.
				AddBodyForce(Vec3(-Sign(U) * (Friction + Residuary + WaveResistance) * (U < 0.0 ? 1.6 : 1.0), 0.0, 0.0), HullPoint);
			}
			// Cross-flow drag at two stations: sway resistance and yaw damping at low speed.
			const double Share = Vol / std::max(DesignVolume, 1e-6);
			for (double StationX : { 0.328 * Lwl, -0.328 * Lwl })
			{
				const Vec3 P(StationX, Hull.CenterY, -0.12);
				const double VY = Q.Unrotate(PointVelocityThroughWater(P)).Y;
				AddBodyForce(Vec3(0.0, -0.5 * kWaterDensity * C.HullLateralCd * C.HullLateralArea * Share * VY * std::fabs(VY), 0.0), P);
			}
		}
		{
			// Munk moment: the canoe body wants to turn broadside to its motion (part of weather helm).
			const Vec3 CGVelBody = Q.Unrotate(State.Velocity - WaterCurrent);
			TorqueBody.Z += -C.MunkAddedMass * CGVelBody.X * CGVelBody.Y;
			if (C.HeelYawCoef > 0.0 && !C.Hulls.empty())
			{
				// Heel-induced yaw toward windward (positive heel = heeled to port, wind from starboard: bow to starboard).
				const double L = C.Hulls[0].WaterlineLength();
				const double Heel = Clamp(Q.Heel(), -60.0 * kDegToRad, 60.0 * kDegToRad);
				TorqueBody.Z += C.HeelYawCoef * 0.5 * kWaterDensity * CGVelBody.X * std::fabs(CGVelBody.X) * L * L * HullDepth() * std::sin(Heel);
			}
			TorqueBody.Z += -C.YawDampingLinear * State.AngularVelocity.Z;
			TorqueBody.X += -C.ExtraRollDamping * State.AngularVelocity.X;
		}

		// Engines: thrust lags the throttle by about a second; it falls off toward the propeller's pitch speed.
		double PropWash[8] = { 0, 0, 0, 0, 0, 0, 0, 0 };
		double PropWashX[8] = { 0, 0, 0, 0, 0, 0, 0, 0 };
		// Twin engines: the split runs one ahead and one astern. With the throttle in neutral the skipper balances
		// them (the one going ahead is eased to match the weaker one astern), so the boat pivots in place.
		const bool bPivot = C.Engines.size() >= 2 && std::fabs(Controls.Throttle) < 0.05 && std::fabs(Controls.ThrottleSplit) > 0.0;
		for (int E = 0; E < int(C.Engines.size()) && E < 4; ++E)
		{
			const FEngineDef& Eng = C.Engines[E];
			double Throttle = Clamp(Controls.Throttle, -1.0, 1.0);
			if (C.Engines.size() >= 2) Throttle = Clamp(Throttle + (Eng.Position.Y < 0.0 ? 1.0 : -1.0) * Controls.ThrottleSplit, -1.0, 1.0);
			if (bPivot && Throttle > 0.0) Throttle *= Eng.ReverseFraction;
			const double Target = Throttle * Eng.MaxThrustN * (Throttle < 0.0 ? Eng.ReverseFraction : 1.0);
			State.EngineThrust[E] = MoveToward(State.EngineThrust[E], Target, Eng.MaxThrustN * Dt);
			const double T = State.EngineThrust[E];
			if (std::fabs(T) < 1e-3) continue;
			const double U = Q.Unrotate(PointVelocityThroughWater(Eng.Position)).X;
			const double Vp = Eng.PropSpeedKnots * kKnot;
			// Astern the propeller works backward through its own wake: the thrust is gone by about half the pitch speed.
			const double Eff = T > 0.0 ? std::max(0.0, 1.0 - (U / Vp) * std::fabs(U / Vp)) : std::max(0.0, 1.0 - (U < 0.0 ? (U / (0.5 * Vp)) * (U / (0.5 * Vp)) : 0.0));
			// The propeller has to be in the water to push.
			const Vec3 PropWorld = Origin + Q.Rotate(Eng.Position);
			const double Submerged = Clamp((WaterAt(PropWorld) - PropWorld.Z) / 0.2, 0.0, 1.0);
			const double Thrust = T * Eff * Submerged;
			const double Walk = T < 0.0 ? -Eng.PropWalk * std::fabs(Thrust) : 0.0; // right-handed prop astern: stern to port
			AddBodyForce(Vec3(Thrust, Walk, 0.0), Eng.Position);
			if (Thrust > 0.0 && Eng.Hull < 8)
			{
				// Slipstream over a rudder just aft: steerage at low speed, the way you kick the stern around a dock.
				const double Disc = 0.25 * kPi * Eng.PropDiameter * Eng.PropDiameter;
				PropWash[Eng.Hull] = std::max(PropWash[Eng.Hull], 0.5 * std::sqrt(2.0 * Thrust / (kWaterDensity * Disc)));
				PropWashX[Eng.Hull] = Eng.Position.X;
			}
		}

		// Keels, boards and rudders.
		double Hinge = 0.0;
		{
			double HullDownwash[8] = { 0, 0, 0, 0, 0, 0, 0, 0 };
			bool bHasDownwash[8] = { false, false, false, false, false, false, false, false };
			const double Board = Clamp(Controls.Board, 0.0, 1.0);
			auto Immersion = [&](const FFoilParams& P)
			{
				const double Half = 0.5 * P.Area / std::max(P.Chord, 1e-3);
				const Vec3 Root = Origin + Q.Rotate(P.Center + Vec3(0, 0, Half));
				const Vec3 Tip = Origin + Q.Rotate(P.Center - Vec3(0, 0, Half));
				const double Water = WaterAt(Origin + Q.Rotate(P.Center));
				const double Low = std::min(Root.Z, Tip.Z), High = std::max(Root.Z, Tip.Z);
				if (High - Low < 0.05) return Low < Water ? 1.0 : 0.0;
				return Clamp((Water - Low) / (High - Low), 0.0, 1.0);
			};
			for (int Pass = 0; Pass < 2; ++Pass) // lifting foils first (their downwash reaches the rudders)
			{
				for (const FFoilDef& F : C.Foils)
				{
					const bool bRudder = F.Role == EFoilRole::Rudder;
					if (bRudder != (Pass == 1)) continue;
					FFoilParams P = F.Params;
					if (F.bRetractable)
					{
						if (Board < 0.02) continue;
						const double Span = F.Span();
						P.Area *= Board;
						P.Center.Z += 0.5 * (1.0 - Board) * Span;
					}
					const double Wet = Immersion(P);
					if (Wet <= 0.0) continue;
					const double Vent = 1.0 - F.VentDepth * SmoothStep(F.VentStartDeg * kDegToRad, F.VentEndDeg * kDegToRad, HeelAbs);
					Vec3 Flow = -Q.Unrotate(PointVelocityThroughWater(P.Center));
					FFoilResult R;
					if (!bRudder)
					{
						R = ComputeFoil(P, Flow, Vec3(-1, 0, 0), kWaterDensity, Vent);
						if (F.Hull < 8 && !bHasDownwash[F.Hull])
						{
							bHasDownwash[F.Hull] = true;
							HullDownwash[F.Hull] = C.KeelDownwashFactor * 2.0 * R.LiftCoefficient / (kPi * P.EffectiveAspectRatio);
						}
					}
					else
					{
						// The rudder sits in the keel's wake: the keel turns the flow by its downwash angle, so the rudder
						// sees less leeway than the keel does. That is why a boat carries weather helm.
						const double Downwash = F.Hull < 8 ? HullDownwash[F.Hull] : 0.0;
						const double Cs = std::cos(-Downwash), Sn = std::sin(-Downwash);
						Flow = Vec3(Flow.X * Cs - Flow.Y * Sn, Flow.X * Sn + Flow.Y * Cs, Flow.Z);
						if (F.Hull < 8 && PropWash[F.Hull] > 0.0 && PropWashX[F.Hull] - P.Center.X < 3.0 && PropWashX[F.Hull] > P.Center.X - 0.5)
						{
							Flow.X -= PropWash[F.Hull];
						}
						const Vec3 Chord(-std::cos(State.RudderAngle), std::sin(State.RudderAngle), 0.0);
						R = ComputeFoil(P, Flow, Chord, kWaterDensity, Vent);
						const double Speed = Vec3(Flow.X, Flow.Y, 0.0).Length();
						Hinge += R.LiftCoefficient * 0.5 * kWaterDensity * Speed * Speed * P.Area * Wet * C.RudderStockToCP;
					}
					AddBodyForce(R.Force * Wet, P.Center);
				}
			}
		}

		// Sails and windage.
		ComputeSails(Dt, Controls, Wind, ForceBody, TorqueBody);

		// Rig in the water (capsized): the sails and mast drag through the water and the sealed mast floats a little.
		{
			const Vec3 MastBase = Vec3(C.MastX, 0.0, C.BoomZ);
			const int N = 6;
			// The rig reaches as high as the sail does (a lateen's yard stands well above its short mast).
			const double RigTopZ = std::max(C.MastheadZ, C.Main.NumStrips > 0 ? C.Main.Strips[C.Main.NumStrips - 1].ZTop : C.MastheadZ);
			const double SegLen = (RigTopZ - C.BoomZ) / N;
			const double MastSegVol = 0.25 * kPi * C.MastDiameter * C.MastDiameter * SegLen;
			const double SparSegVol = 0.001 * C.SparFloatLiters / N;
			for (int I = 0; I < N; ++I)
			{
				const Vec3 Body = MastBase + Vec3(0.0, 0.0, (I + 0.5) * SegLen);
				const double SegVol = (Body.Z <= C.MastheadZ ? MastSegVol : 0.0) + SparSegVol;
				const Vec3 P = Origin + Q.Rotate(Body);
				const double Depth = WaterAt(P) - P.Z;
				if (Depth <= 0.0) continue;
				const double Wet = Clamp(Depth / 0.3, 0.0, 1.0);
				const Vec3 Vel = State.Velocity + OmegaWorld.Cross(P - CGWorld) - WaterCurrent;
				// The sail beside this part of the mast acts as a large flat plate in the water.
				const double PlateArea = (C.Main.TotalArea + (C.HasJib() ? C.Jib.TotalArea : 0.0)) / N;
				// Quadratic drag, capped at what one step can take out of this point's motion: the masthead of a dinghy
				// has an effective mass of a couple of kilograms, so uncapped drag would overshoot and blow up.
				const Vec3 R = P - CGWorld;
				const double R2 = R.X * R.X + R.Y * R.Y + R.Z * R.Z;
				const double PointMass = 1.0 / (1.0 / Mass + R2 / std::min(EffectiveInertia.X, EffectiveInertia.Y));
				// A sail lying on the water sinks only as fast as the water can flow round a plate that size, so slow motion
				// is resisted too (drag on at least 0.6 m/s): a capsized dinghy lies on her side for a while before she
				// turns turtle, as in the Phase 8 references (SUN-S-004, SUN-S-006, H16-C-004).
				const double Coef = std::min(0.5 * kWaterDensity * 1.2 * PlateArea * std::max(Vel.Length(), 0.6) * Wet, 0.3 * PointMass / Dt);
				const Vec3 Drag = Vel * -Coef;
				AddWorldForce(Drag + Vec3(0.0, 0.0, kWaterDensity * kGravity * SegVol * Wet), P);
			}
		}

		// Contact: the bottom (grounding), docks and bridges, dock lines.
		Telemetry.bAground = false;
		Telemetry.bCollision = false;
		Telemetry.DepthUnderKeel = 100.0;
		auto Contact = [&](const Vec3& PointWorld, const Vec3& Normal, double Penetration, double Stiffness, double Damping, double Friction, const Vec3& SurfaceVel = Vec3())
		{
			const Vec3 Vel = State.Velocity + OmegaWorld.Cross(PointWorld - CGWorld) - SurfaceVel;
			const double Vn = Vel.Dot(Normal);
			const double Fn = std::max(0.0, Stiffness * Penetration - Damping * Vn);
			const Vec3 Vt = Vel - Normal * Vn;
			const double VtLen = Vt.Length();
			// Regularized Coulomb friction: smooth near zero slip so a grounded boat settles instead of jittering.
			const Vec3 Ft = VtLen > 1e-6 ? Vt * (-Friction * Fn / std::max(VtLen, 0.05)) * std::min(1.0, VtLen / 0.05) : Vec3();
			AddWorldForce(Normal * Fn + Ft, PointWorld);
		};
		const double ContactScale = std::max(1.0, Mass / 1052.0); // stiffer contacts for heavier boats, same feel
		if (Terrain && Terrain->IsValid())
		{
			for (const Vec3& B : BottomPoints)
			{
				const Vec3 P = Origin + Q.Rotate(B);
				const double Ground = Terrain->HeightAt(P.X, P.Y);
				Telemetry.DepthUnderKeel = std::min(Telemetry.DepthUnderKeel, P.Z - Ground);
				if (P.Z < Ground)
				{
					// Soft lake mud: firm enough to stop the boat, with a lot of friction.
					const double GX = (Terrain->HeightAt(P.X + 1.0, P.Y) - Terrain->HeightAt(P.X - 1.0, P.Y)) * 0.5;
					const double GY = (Terrain->HeightAt(P.X, P.Y + 1.0) - Terrain->HeightAt(P.X, P.Y - 1.0)) * 0.5;
					// Penetration capped: a boat put down inside the bank is eased out, not fired out.
					Contact(P, Vec3(-GX, -GY, 1.0).Normalized(), std::min(Ground - P.Z, 0.3), 2.5e5 * ContactScale, 3.0e4 * ContactScale, 0.8);
					Telemetry.bAground = true;
				}
			}
		}
		if (Obstacles && !Obstacles->empty() && ObstacleRows > 0)
		{
			for (const Vec3& HP : OutlinePoints)
			{
				const Vec3 P = Origin + Q.Rotate(HP);
				const int BR = int(std::floor((P.X - ObstacleX0) / ObstacleCell)), BC = int(std::floor((P.Y - ObstacleY0) / ObstacleCell));
				if (BR < 0 || BC < 0 || BR >= ObstacleRows || BC >= ObstacleCols) continue;
				for (const int SegmentIndex : ObstacleBuckets[size_t(BR) * ObstacleCols + BC])
				{
					const FObstacleSegment& S = (*Obstacles)[SegmentIndex];
					if (P.Z < S.Bottom || P.Z > S.Top) continue;
					const double SX = S.BX - S.AX, SY = S.BY - S.AY;
					const double Len2 = SX * SX + SY * SY;
					const double T = Len2 > 1e-9 ? Clamp(((P.X - S.AX) * SX + (P.Y - S.AY) * SY) / Len2, 0.0, 1.0) : 0.0;
					const double CX = S.AX + SX * T, CY = S.AY + SY * T;
					const double DX = P.X - CX, DY = P.Y - CY;
					const double Dist = std::sqrt(DX * DX + DY * DY);
					const double Pen = S.Radius + 0.1 - Dist;
					if (Pen > 0.0 && Dist > 1e-6)
					{
						Contact(P, Vec3(DX / Dist, DY / Dist, 0.0), Pen, 1.5e5 * ContactScale, 2.0e4 * ContactScale, 0.3);
						Telemetry.bCollision = true;
					}
				}
			}
		}
		// Other vessels: the same contact as a dock, moving with the other hull (a fender-off, not a crash model).
		Telemetry.bVesselContact = false;
		for (const FObstacleSegment& S : MovingObstacles)
		{
			for (const Vec3& HP : OutlinePoints)
			{
				const Vec3 P = Origin + Q.Rotate(HP);
				if (P.Z < S.Bottom || P.Z > S.Top) continue;
				const double SX = S.BX - S.AX, SY = S.BY - S.AY;
				const double Len2 = SX * SX + SY * SY;
				const double T = Len2 > 1e-9 ? Clamp(((P.X - S.AX) * SX + (P.Y - S.AY) * SY) / Len2, 0.0, 1.0) : 0.0;
				const double DX = P.X - (S.AX + SX * T), DY = P.Y - (S.AY + SY * T);
				const double Dist = std::sqrt(DX * DX + DY * DY);
				const double Pen = S.Radius + 0.1 - Dist;
				if (Pen > 0.0 && Dist > 1e-6)
				{
					Contact(P, Vec3(DX / Dist, DY / Dist, 0.0), Pen, 1.5e5 * ContactScale, 2.0e4 * ContactScale, 0.3, Vec3(S.VX, S.VY, 0.0));
					Telemetry.bCollision = true;
					Telemetry.bVesselContact = true;
				}
			}
		}
		for (const FMooringLine& Line : Mooring)
		{
			const Vec3 P = Origin + Q.Rotate(Line.BodyPoint);
			const Vec3 D = Line.Anchor - P;
			const double Dist = D.Length();
			if (Dist > Line.Length && Dist > 1e-6)
			{
				const Vec3 Dir = D / Dist;
				const Vec3 Vel = State.Velocity + OmegaWorld.Cross(P - CGWorld);
				// Nylon dock line: stretchy, with damping only while it is being pulled tighter.
				const double Tension = (6000.0 * (Dist - Line.Length) + 1500.0 * std::max(0.0, -Vel.Dot(Dir))) * ContactScale;
				AddWorldForce(Dir * Tension, P);
			}
		}

		// Combine and integrate (semi-implicit Euler). Added mass and inertia act along body axes.
		ForceWorld += Q.Rotate(ForceBody);
		const Vec3 TorqueTotalBody = Q.Unrotate(TorqueWorld) + TorqueBody;
		const Vec3 AccelBody = Q.Unrotate(ForceWorld).Div(EffectiveMass);
		State.Velocity += Q.Rotate(AccelBody) * Dt;

		const Vec3& W = State.AngularVelocity;
		const Vec3 Gyro = W.Cross(Inertia.Mul(W));
		const Vec3 AngularAccel = (TorqueTotalBody - Gyro).Div(EffectiveInertia);
		State.AngularVelocity += AngularAccel * Dt;
		{
			// Crew C1: the accelerations the crew feel against gravity, smoothed over 25 ms.
			const double K = std::min(1.0, Dt / 0.025);
			Telemetry.AccelBody += (AccelBody - Telemetry.AccelBody) * K;
			Telemetry.AngularAccelBody += (AngularAccel - Telemetry.AngularAccelBody) * K;
		}

		State.Position += State.Velocity * Dt;
		const Vec3& W2 = State.AngularVelocity;
		const Quat Spin = State.Orientation * Quat(W2.X, W2.Y, W2.Z, 0.0);
		State.Orientation = Quat(
			State.Orientation.X + 0.5 * Spin.X * Dt, State.Orientation.Y + 0.5 * Spin.Y * Dt,
			State.Orientation.Z + 0.5 * Spin.Z * Dt, State.Orientation.W + 0.5 * Spin.W * Dt).Normalized();

		// Rudder: the helm holds the tiller with finite stiffness, so the rudder's hinge moment pushes it
		// toward streaming with the flow. That offset is the weather (or lee) helm you feel.
		const double Commanded = Clamp(Controls.Tiller, -1.0, 1.0) * C.MaxRudderAngleDeg * kDegToRad;
		const double RudderTarget = Clamp(Commanded - Hinge / C.HelmStiffness, -C.MaxRudderAngleDeg * kDegToRad, C.MaxRudderAngleDeg * kDegToRad);
		State.RudderAngle += (RudderTarget - State.RudderAngle) * std::min(1.0, Dt / C.RudderResponseTime);

		// Crew: to the windward side, sitting, hiking or out on the trapeze; on the board (or the righting line)
		// to bring a capsized boat back up.
		const double HeelNow = Q.Heel();
		const double TiltNow = Q.Tilt(); // like |heel|, but reads 180 deg turned turtle (the heel reads near 0 there)
		double TargetY, TargetZ = 0.0;
		const bool bRighting = Controls.bRighting && C.RightingLever > 0.0 && TiltNow > 50.0 * kDegToRad;
		if (bRighting && TiltNow > 150.0 * kDegToRad && !C.bMultihull)
		{
			// Turned turtle: stand on the edge of the upturned hull and lean right back on the board, which pulls her
			// onto her side first (then the usual righting below brings her up).
			TargetY = (HeelNow >= 0.0 ? 1.0 : -1.0) * (0.5 * C.Beam + 1.6 * C.RightingLever);
			TargetZ = -1.2 * C.RightingLever;
		}
		else if (bRighting)
		{
			// Heeled to port (positive heel): the port hull (or the port side) is down.
			double DownHullY = 0.0;
			for (const FHullShape& Hull : C.Hulls) if (HeelNow > 0.0 ? Hull.CenterY < DownHullY : Hull.CenterY > DownHullY) DownHullY = Hull.CenterY;
			TargetY = DownHullY;
			TargetZ = -C.RightingLever;
		}
		else if (TiltNow > 60.0 * kDegToRad)
		{
			// On its side: the crew has fallen in, or is hanging on at the centerline, until they try to right her.
			TargetY = 0.0;
		}
		else
		{
			const double Hike = Clamp(Controls.Hike, -1.0, 1.0);
			TargetY = State.WindwardSide * (Hike >= 0.0 ? C.CrewSitOut + C.CrewHikeOut * Hike : C.CrewSitOut * (1.0 + 2.0 * Hike));
		}
		// Fore and aft: dinghies only (the rest have nowhere to go), and only sailing (not righting or capsized).
		const double TargetX = bRighting || TiltNow > 60.0 * kDegToRad ? 0.0 : -Clamp(Controls.CrewAft, 0.0, 1.0) * C.CrewAftRange;
		State.CrewOffset = MoveToward(State.CrewOffset, TargetY, C.CrewMoveSpeed * Dt);
		State.CrewOffsetZ = MoveToward(State.CrewOffsetZ, TargetZ, C.CrewMoveSpeed * Dt);
		State.CrewOffsetX = MoveToward(State.CrewOffsetX, TargetX, 0.5 * C.CrewMoveSpeed * Dt);

		State.Time += Dt;

		// Telemetry.
		FBoatTelemetry& T = Telemetry;
		const Vec3 VelBody = Q.Unrotate(State.Velocity);
		T.BoatSpeed = State.Velocity.LengthXY();
		T.ForwardSpeed = VelBody.X;
		T.Heading = Q.Heading();
		T.Heel = Q.Heel();
		T.Pitch = Q.Pitch();
		// Leeway is measured through the water (what the keel feels); course over ground includes the current.
		const Vec3 VelWater = State.Velocity - WaterCurrent;
		T.SpeedThroughWater = Q.Unrotate(VelWater).X;
		T.Leeway = VelWater.LengthXY() > 0.2 ? WrapAngle(std::atan2(VelWater.Y, VelWater.X) - T.Heading) : 0.0;
		T.CourseOverGround = T.BoatSpeed > 0.05 ? std::atan2(State.Velocity.Y, State.Velocity.X) : T.Heading;
		const Vec3 TrueWind = Wind.VelocityAt(Vec3(CGWorld.X, CGWorld.Y, 10.0), State.Time);
		T.TrueWindSpeed = TrueWind.LengthXY();
		const double WindFrom = std::atan2(-TrueWind.Y, -TrueWind.X);
		T.TrueWindAngle = WrapAngle(WindFrom - T.Heading);
		T.VMG = T.TrueWindSpeed > 1e-3 ? State.Velocity.Dot(-TrueWind / T.TrueWindSpeed) : 0.0;
		const Vec3 Masthead = Vec3(C.MastX, 0.0, C.MastheadZ);
		const Vec3 MastheadWorld = BodyToWorld(Masthead);
		T.MastheadWindBody = Q.Unrotate(Wind.VelocityAt(MastheadWorld, State.Time) - PointVelocityWorld(Masthead));
		T.ApparentWindSpeed = T.MastheadWindBody.LengthXY();
		T.ApparentWindAngle = std::atan2(-T.MastheadWindBody.Y, -T.MastheadWindBody.X);
		T.RudderAngle = State.RudderAngle;
		// Weather helm: the hinge moment pushes the rudder toward turning the bow into the wind (the helm must hold it).
		T.HelmForce = -(Hinge / C.TillerLength) * State.WindwardSide;
		T.bInIrons = std::fabs(T.TrueWindAngle) < 35.0 * kDegToRad && T.ForwardSpeed < 0.5 * kKnot;
		T.Froude = T.BoatSpeed / std::sqrt(kGravity * std::max(C.WaterlineLength, 0.5));
		bool bAnyPlaning = false;
		for (const FHullShape& Hull : C.Hulls) bAnyPlaning |= Hull.PlaningLift > 0.0;
		T.bPlaning = (bAnyPlaning || C.bMultihull) && MaxFroude > 0.65 && HeelAbs < 40.0 * kDegToRad;
		T.bFlyingHull = false;
		if (C.bMultihull && NumHulls >= 2)
		{
			// A catamaran flies its windward hull; a trimaran its main hull (the windward ama is always up).
			if (NumHulls == 2)
			{
				for (int H = 0; H < 2; ++H) T.bFlyingHull |= HullVolume[H] < 0.01 * DesignVolume;
			}
			else
			{
				T.bFlyingHull = HullVolume[0] < 0.02 * DesignVolume;
			}
		}
		// Lying on her side or turned turtle (the heel alone reads near zero upside down).
		State.CapsizedTime = Q.Tilt() > 70.0 * kDegToRad ? State.CapsizedTime + Dt : 0.0;
		T.bCapsized = State.CapsizedTime > 2.0;

		// Windward side with hysteresis, from the apparent wind over the moving boat at masthead height. Not from the
		// masthead's own motion: a rolling mast swings the wind there from side to side, and a crew that followed it
		// would rock the boat (in a calm she rocked herself up to a knot). Not while knocked flat either.
		const Vec3 CrewWind = Q.Unrotate(Wind.VelocityAt(MastheadWorld, State.Time) - State.Velocity);
		const double CrewAwa = std::atan2(-CrewWind.Y, -CrewWind.X);
		if (CrewWind.LengthXY() > 0.5 && std::fabs(CrewAwa) > 15.0 * kDegToRad && std::fabs(CrewAwa) < 165.0 * kDegToRad && HeelAbs < 45.0 * kDegToRad)
		{
			State.WindwardSide = CrewAwa > 0.0 ? 1 : -1;
		}
	}

	void FBoatModel::ComputeSails(double Dt, const FBoatControls& Controls, const FWindField& Wind, Vec3& ForceBody, Vec3& TorqueBody)
	{
		// Reefs: rebuild the main when the crew takes one in or shakes one out.
		const int WantReef = std::max(0, std::min(Controls.Reef, int(Config.ReefLuffFraction.size())));
		if (WantReef != State.Reef)
		{
			Config.BuildMain(WantReef);
			State.Reef = WantReef;
		}

		const FBoatConfig& C = Config;
		const Quat& Q = State.Orientation;
		FBoatTelemetry& T = Telemetry;
		const bool bSpin = Controls.bSpinnaker && C.HasSpinnaker();
		T.NumMainStrips = C.Main.NumStrips;
		T.NumJibStrips = C.Jib.NumStrips;
		T.NumSpinStrips = bSpin ? C.Spinnaker.NumStrips : 0;
		T.DriveForce = 0.0;
		T.HeelingForce = 0.0;
		const Vec3 Origin = OriginPosition();

		auto Apparent = [&](const Vec3& BodyPoint)
		{
			return Q.Unrotate(Wind.VelocityAt(BodyToWorld(BodyPoint), State.Time) - PointVelocityWorld(BodyPoint));
		};
		auto AngleFrom = [](const Vec3& AirBody) { return std::atan2(-AirBody.Y, -AirBody.X); };

		// Apparent wind angle seen by each sail (mean over its strips at the luff), to decide its side and natural angle.
		auto MeanAngle = [&](const FSailGeometry& Geo)
		{
			Vec3 Sum;
			for (int I = 0; I < Geo.NumStrips; ++I)
			{
				const FSailStripGeometry& S = Geo.Strips[I];
				Sum += Apparent(Vec3(S.LuffX - 0.3 * S.Chord, 0.0, 0.5 * (S.ZBottom + S.ZTop)));
			}
			return AngleFrom(Sum);
		};

		const double MainAWA = MeanAngle(C.Main);
		const double JibAWA = C.HasJib() ? MeanAngle(C.Jib) : MainAWA;
		const double SpinAWA = bSpin ? MeanAngle(C.Spinnaker) : MainAWA;
		auto UpdateSide = [](int& Side, double AWA)
		{
			const double A = std::fabs(AWA);
			if (A > 2.0 * kDegToRad && A < 178.0 * kDegToRad)
			{
				Side = AWA > 0.0 ? -1 : 1; // sail lies on the side away from the wind
			}
		};
		UpdateSide(State.MainSide, MainAWA);
		UpdateSide(State.JibSide, JibAWA);
		UpdateSide(State.SpinSide, SpinAWA);
		// Backing the jib: hold it out on the windward side (heaving to, pushing the bow off when in irons).
		// The sheet holds it on the side it was backed on (the windward side at that moment), whatever the boat does next.
		const bool bBacked = Controls.bBackJib && C.HasJib();
		if (bBacked)
		{
			if (State.BackedJibSide == 0)
			{
				State.BackedJibSide = JibAWA > 0.0 ? 1 : -1; // wind from starboard: jib held to starboard (windward)
			}
			State.JibSide = State.BackedJibSide;
		}
		else
		{
			State.BackedJibSide = 0;
		}
		// Wing-on-wing: deep enough downwind, the jib can be held out on the side opposite the main.
		const bool bWing = !bBacked && !bSpin && Controls.bWingOnWing && std::fabs(JibAWA) > 150.0 * kDegToRad;
		if (bWing)
		{
			State.JibSide = -State.MainSide;
		}

		// Shape from the controls.
		const double MainSheet = Clamp(Controls.MainSheet, 0.0, 1.0);
		const double JibSheet = Clamp(Controls.JibSheet, 0.0, 1.0);
		const double SpinSheet = Clamp(Controls.SpinSheet, 0.0, 1.0);
		const double Vang = Clamp(Controls.Vang, 0.0, 1.0);
		const double Cunningham = Clamp(Controls.Cunningham, 0.0, 1.0);
		const double Outhaul = Clamp(Controls.Outhaul, 0.0, 1.0);
		const double Backstay = Clamp(Controls.Backstay, 0.0, 1.0);

		const double LeechTension = std::max(Vang, Clamp(1.0 - MainSheet / 0.3, 0.0, 1.0));
		const double MainTwist = (2.0 + 20.0 * (1.0 - LeechTension) + 4.0 * Backstay) * kDegToRad;
		const double JibTwist = (5.0 + 10.0 * JibSheet) * kDegToRad;
		const double SpinTwist = (8.0 + 10.0 * SpinSheet) * kDegToRad;

		enum class ESail { Main, Jib, Spin };
		auto Camber = [&](ESail Which, double H)
		{
			double Value;
			if (Which == ESail::Main)
			{
				Value = C.Main.BaseCamber + 0.01 - 0.02 * H - Outhaul * 0.05 * (1.0 - H) * (1.0 - H) - Cunningham * 0.015 - Backstay * 0.04 * H;
			}
			else if (Which == ESail::Jib)
			{
				Value = C.Jib.BaseCamber - Backstay * 0.03 + 0.02 * JibSheet;
			}
			else
			{
				return Clamp(C.Spinnaker.BaseCamber + 0.03 * SpinSheet, 0.10, 0.28);
			}
			return Clamp(Value, 0.04, 0.18);
		};

		// The sheet limits how far the sail can go out; the wind pushes it out to that limit or until it
		// lines up with the flow and luffs. A free sail weathervanes until even its foot (the least twisted part)
		// luffs, so a fully eased sail flogs instead of quietly driving from its lower panels.
		auto NaturalAngle = [&](double AWA, double MeanTwist, double LuffAlpha)
		{
			return std::fabs(AWA) - MeanTwist - LuffAlpha + 2.0 * kDegToRad;
		};
		const double MainLuff = -(0.4 * Camber(ESail::Main, 0.5) + 0.035);
		const double JibLuff = -(0.4 * Camber(ESail::Jib, 0.5) + 0.035);
		const double SpinLuff = -(0.4 * Camber(ESail::Spin, 0.5) + 0.035);
		const double MaxEase = C.MainMaxEaseDeg * kDegToRad;
		const double TravelerAngle = Clamp(Controls.Traveler, -1.0, 1.0) * C.TravelerRangeDeg * kDegToRad;
		const double MainLimit = std::max(TravelerAngle + MainSheet * MaxEase, -4.0 * kDegToRad);
		const double JibMin = C.JibMinAngleDeg * kDegToRad, JibMax = C.JibMaxAngleDeg * kDegToRad;
		const double JibLimit = JibMin + JibSheet * (JibMax - JibMin);
		const double MainTarget = Clamp(std::min(MainLimit, NaturalAngle(MainAWA, 0.0, MainLuff)), -4.0 * kDegToRad, MaxEase);
		const double JibTarget = (bWing || bBacked) ? std::min(JibLimit, JibMax)
			: Clamp(std::min(JibLimit, NaturalAngle(JibAWA, 0.0, JibLuff)), 0.0, JibMax);
		const double SpinLimit = (12.0 + SpinSheet * 85.0) * kDegToRad;
		const double SpinTarget = Clamp(std::min(SpinLimit, NaturalAngle(SpinAWA, 0.0, SpinLuff)), 0.0, 97.0 * kDegToRad);

		State.BoomAngle = MoveToward(State.BoomAngle, State.MainSide * MainTarget, 150.0 * kDegToRad * Dt);
		State.JibAngle = MoveToward(State.JibAngle, State.JibSide * JibTarget, 200.0 * kDegToRad * Dt);
		State.SpinAngle = bSpin ? MoveToward(State.SpinAngle, State.SpinSide * SpinTarget, 200.0 * kDegToRad * Dt) : State.SpinSide * 20.0 * kDegToRad;

		// Blanketing: running, the jib sits in the main's wind shadow; the spinnaker, flying forward, much less so.
		// With the spinnaker up, the jib also sits in the spinnaker's shadow.
		const double JibBlanket = (bWing ? 1.0 : 1.0 - 0.35 * SmoothStep(140.0 * kDegToRad, 170.0 * kDegToRad, std::fabs(JibAWA))) * (bSpin ? 0.55 : 1.0);
		const double SpinBlanket = 1.0 - 0.15 * SmoothStep(150.0 * kDegToRad, 175.0 * kDegToRad, std::fabs(SpinAWA));

		// Foot angle is measured from the centerline toward the sail's side; slightly negative means the boom is
		// pulled a little to windward of the centerline (traveler up in light air).
		auto DoSail = [&](ESail Which, const FSailGeometry& Geo, int Side, double FootAngleSigned, double Twist, double StallDelta,
			double DownwashAlpha, double DownwashMaxZ, double LiftScale, double WindScale, FSailStripState* Out)
		{
			const double Foot = FootAngleSigned * Side;
			double MeanCL = 0.0;
			for (int I = 0; I < Geo.NumStrips; ++I)
			{
				const FSailStripGeometry& G = Geo.Strips[I];
				FSailStripState& S = Out[I];
				const double H = G.HeightFraction;
				S.TwistFromFoot = Twist * std::pow(H, 1.2);
				S.Camber = Camber(Which, H);
				const double Angle = std::min(Foot + S.TwistFromFoot, 100.0 * kDegToRad);
				S.AngleFromCenterline = Side * Angle;
				const Vec3 Chord = SailChordDir(Angle, Side);
				S.CenterOfEffort = Vec3(G.LuffX, 0.0, 0.5 * (G.ZBottom + G.ZTop)) + Chord * (0.42 * G.Chord);

				// A strip in the water (capsized) carries no wind; the rig drag in the water is handled with the mast.
				const Vec3 CoEWorld = Origin + Q.Rotate(S.CenterOfEffort);
				const double Dry = 1.0 - Clamp((WaterHeightAt(CoEWorld.X, CoEWorld.Y) - CoEWorld.Z) / 0.3 + 0.5, 0.0, 1.0);
				const Vec3 Air = Apparent(S.CenterOfEffort) * WindScale;
				const Vec3 U(Air.X, Air.Y, 0.0);
				const double Speed = U.Length();
				S.ApparentSpeed = Speed;
				S.ApparentAngle = AngleFrom(Air);
				if (Speed < 1e-3 || Dry <= 0.0)
				{
					S.Force = Vec3();
					S.LiftCoefficient = S.DragCoefficient = 0.0;
					S.Flow = ESailFlow::Luffing;
					continue;
				}
				const double Alpha = std::atan2(Chord.X * U.Y - Chord.Y * U.X, Chord.X * U.X + Chord.Y * U.Y);
				S.AlphaN = -Side * Alpha;
				if (S.CenterOfEffort.Z < DownwashMaxZ)
				{
					S.AlphaN -= DownwashAlpha;
				}
				double CL, CD;
				SailCoefficients(Geo, S.AlphaN, S.Camber, StallDelta, CL, CD, S.LuffAlpha, S.StallAlpha, S.Flow);
				CL *= LiftScale;
				S.LiftCoefficient = CL;
				S.DragCoefficient = CD;
				MeanCL += std::max(CL, 0.0) / Geo.NumStrips;

				const double Q2 = 0.5 * kAirDensity * Speed * Speed * G.Area * Dry;
				const Vec3 FlowDir = U / Speed;
				const Vec3 LiftDir(-FlowDir.Y, FlowDir.X, 0.0);
				S.Force = LiftDir * (-Side * CL * Q2) + FlowDir * (CD * Q2);
				ForceBody += S.Force;
				TorqueBody += (S.CenterOfEffort - CenterOfGravity).Cross(S.Force);
				T.DriveForce += S.Force.X;
				T.HeelingForce += S.Force.Y;
			}
			return MeanCL;
		};

		double JibHeadZ = 0.0, Downwash = 0.0;
		if (C.HasJib())
		{
			JibHeadZ = C.Jib.Strips[C.Jib.NumStrips - 1].ZTop;
			const double JibUpwash = 1.0 + 0.08 * Clamp(MainMeanLift / 1.4, 0.0, 1.0);
			const double JibCL = DoSail(ESail::Jib, C.Jib, State.JibSide, State.JibAngle, JibTwist, 0.0, 0.0, 0.0, JibUpwash, JibBlanket, T.JibStrips);
			Downwash = 0.05 * JibCL;
		}
		if (bSpin)
		{
			DoSail(ESail::Spin, C.Spinnaker, State.SpinSide, State.SpinAngle, SpinTwist, 0.0, 0.0, 0.0, 1.0, SpinBlanket, T.SpinStrips);
		}
		MainMeanLift = DoSail(ESail::Main, C.Main, State.MainSide, State.BoomAngle, MainTwist, Cunningham * 2.0 * kDegToRad, Downwash, JibHeadZ, 1.0, 1.0, T.MainStrips);

		// Windage of the mast, rigging, topsides and crew.
		const FHullShape& Hull = C.Hulls.front();
		for (const auto& [Point, CdA] : { std::pair<Vec3, double>(Vec3(C.MastX, 0.0, 0.432 * C.MastheadZ), C.RigWindageCdA),
			std::pair<Vec3, double>(Vec3(Hull.WaterlineMidX - 0.35, 0.0, Hull.SheerZ + 0.18), C.HullWindageCdA) })
		{
			const Vec3 Air = Apparent(Point);
			const Vec3 U(Air.X, Air.Y, 0.0);
			const Vec3 F = U * (0.5 * kAirDensity * CdA * U.Length());
			ForceBody += F;
			TorqueBody += (Point - CenterOfGravity).Cross(F);
		}
	}
}
