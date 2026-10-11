#include "BoatModel.h"
#include <utility>

namespace Sailing
{
	namespace
	{
		// Body-frame hull geometry helpers (J/22-like: fine bow, flat run aft, wide transom).
		constexpr double kBowX = 3.45, kSternX = -3.41;
		constexpr double kWaterlineMidX = -0.15, kWaterlineHalf = 2.895;

		double SheerHeight(double X) { return 0.62 + 0.10 * std::max(0.0, (X - 1.0) / 2.45); }

		double DeckHalfBeam(double X)
		{
			if (X > -0.4)
			{
				const double U = (X + 0.4) / (kBowX + 0.4 + 0.02);
				return 1.22 * std::sqrt(std::max(0.0, 1.0 - U * U));
			}
			const double U = (-0.4 - X) / 3.0;
			return 1.22 - 0.27 * U * U;
		}

		/** Canoe-body depth below the waterline at a station; negative above the overhangs. */
		double KeelLineDepth(double X, double DMax)
		{
			const double U = (X - kWaterlineMidX) / kWaterlineHalf;
			if (std::fabs(U) <= 1.0)
			{
				return DMax * (1.0 - U * U);
			}
			return -(std::fabs(U) - 1.0) * kWaterlineHalf * (U > 0.0 ? 1.1 : 0.5);
		}

		/** Flat-bottomed section with a firm turn of the bilge, reaching the sheer at the deck edge. */
		double HullBottomZ(double X, double Y, double DMax)
		{
			const double D = KeelLineDepth(X, DMax);
			const double B = std::max(DeckHalfBeam(X), 1e-3);
			const double R = std::min(std::fabs(Y) / B, 1.0);
			const double R4 = R * R * R * R;
			return -D + (D + SheerHeight(X)) * R4;
		}

		// Residuary (wave-making) resistance per unit displacement weight against Froude number.
		// Shape follows the Delft series for a light-displacement keelboat; tuned against the J/22 polar.
		constexpr double kFroude[] =     { 0.00,   0.10,   0.15,   0.20,   0.25,   0.30,   0.35,   0.40,   0.45,   0.50,   0.55,   0.60,   0.70,   0.80 };
		constexpr double kResiduary[] =  { 0.0000, 0.0002, 0.0005, 0.0012, 0.0025, 0.0050, 0.0100, 0.0220, 0.0480, 0.0800, 0.1000, 0.1100, 0.1200, 0.1250 };

		void BuildSail(FSailGeometry& Sail, int NumStrips, double ZFoot, double ZHead, double FootChord, double HeadChord,
			double RoachFraction, double LuffXFoot, double LuffXHead, double TargetArea)
		{
			Sail.NumStrips = NumStrips;
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
	}

	FBoatConfig::FBoatConfig()
	{
		// Fin keel, 3 ft 10 in draft. The canoe body's own side force is folded into the keel's area.
		Keel.Center = Vec3(0.70, 0.0, -0.70); // swept fin, leading edge under the mast; canoe-body lift folded in
		Keel.Area = 0.95;
		Keel.Chord = 0.80;
		Keel.EffectiveAspectRatio = 3.0;
		Keel.StallAngleDeg = 16.0;
		Keel.ProfileDrag = 0.008;

		// Transom-hung rudder.
		Rudder.Center = Vec3(-3.00, 0.0, -0.45);
		Rudder.Area = 0.34;
		Rudder.Chord = 0.36;
		Rudder.EffectiveAspectRatio = 3.0;
		Rudder.StallAngleDeg = 14.0;
		Rudder.ProfileDrag = 0.008;

		// Fractional sloop: P 25.0 ft, E 9.75 ft, I 26.0 ft, J 8.0 ft. 223 sq ft (20.7 m^2) main + 100% jib.
		BuildSail(Main, 4, 1.45, 9.05, 2.97, 0.45, 0.12, MastX - 0.05, MastX - 0.05, 11.5);
		Main.LiftSlope = 3.65;
		Main.InducedAspectRatio = 4.5;
		Main.BaseCamber = 0.12;

		BuildSail(Jib, 4, 0.75, 8.25, 2.75, 0.12, 0.0, 3.40, 1.20, 9.2);
		Jib.LiftSlope = 4.1;
		Jib.InducedAspectRatio = 4.5;
		Jib.BaseCamber = 0.13;
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
		Reset(0.0, 0.0, 0.0, 0.0);
	}

	double FBoatModel::SubmergedVolumeUpright(double Depth) const
	{
		const int NX = 26, NY = 12;
		const double DX = (kBowX - kSternX) / NX;
		double Volume = 0.0;
		for (int I = 0; I < NX; ++I)
		{
			const double X = kSternX + DX * (I + 0.5);
			const double B = DeckHalfBeam(X);
			const double DY = 2.0 * B / NY;
			for (int J = 0; J < NY; ++J)
			{
				const double Y = -B + DY * (J + 0.5);
				Volume += std::max(0.0, -HullBottomZ(X, Y, Depth)) * DX * DY;
			}
		}
		return Volume;
	}

	void FBoatModel::BuildHull()
	{
		// Find the canoe-body depth that floats the boat (with crew) at the design waterline.
		const double Target = Mass / kWaterDensity;
		double Lo = 0.05, Hi = 1.0;
		for (int I = 0; I < 50; ++I)
		{
			const double Mid = 0.5 * (Lo + Hi);
			(SubmergedVolumeUpright(Mid) < Target ? Lo : Hi) = Mid;
		}
		CanoeDepth = 0.5 * (Lo + Hi);

		Columns.clear();
		const int NX = 26, NY = 12;
		const double DX = (kBowX - kSternX) / NX;
		for (int I = 0; I < NX; ++I)
		{
			const double X = kSternX + DX * (I + 0.5);
			const double B = DeckHalfBeam(X);
			const double DY = 2.0 * B / NY;
			for (int J = 0; J < NY; ++J)
			{
				const double Y = -B + DY * (J + 0.5);
				const double ZB = HullBottomZ(X, Y, CanoeDepth);
				const double ZT = SheerHeight(X);
				if (ZT - ZB > 0.02)
				{
					Columns.push_back({ X, Y, ZB, ZT, DX * DY });
				}
			}
		}
	}

	void FBoatModel::Reset(double X, double Y, double Heading, double Speed)
	{
		State = FBoatState();
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
		const int N = int(sizeof(kFroude) / sizeof(kFroude[0]));
		if (Froude >= kFroude[N - 1])
		{
			return kResiduary[N - 1];
		}
		for (int I = 1; I < N; ++I)
		{
			if (Froude < kFroude[I])
			{
				const double T = (Froude - kFroude[I - 1]) / (kFroude[I] - kFroude[I - 1]);
				return Lerp(kResiduary[I - 1], kResiduary[I], T);
			}
		}
		return kResiduary[N - 1];
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
				if (Bottom.Z >= 0.0) continue;
				const double F = Clamp(-Bottom.Z / (Top.Z - Bottom.Z), 0.0, 1.0);
				const double Vol = C.Area * (C.ZTop - C.ZBottom) * F;
				const Vec3 P = Bottom + (Top - Bottom) * (0.5 * F) - Vec3(0, 0, CenterOfGravity.Z - Sink);
				OutVolume += Vol;
				OutMomentX += P.Y * Vol; // buoyancy up at lateral offset Y from the CG
			}
		};
		const double Target = Mass / kWaterDensity;
		double Lo = -0.5, Hi = 0.5, Vol = 0.0, MX = 0.0;
		for (int I = 0; I < 50; ++I)
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

	void FBoatModel::Step(double Dt, const FBoatControls& Controls, const FWindField& Wind)
	{
		const FBoatConfig& C = Config;
		const Quat& Q = State.Orientation;
		const Vec3 Origin = OriginPosition();
		const Vec3 CGWorld = State.Position;
		const Vec3 OmegaWorld = Q.Rotate(State.AngularVelocity);

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

		// Hydrostatics and heave/roll/pitch damping: each hull column against the water surface.
		const Vec3 Axis = Q.Up();
		for (const FColumn& Col : Columns)
		{
			const Vec3 Bottom = Origin + Q.Rotate(Vec3(Col.X, Col.Y, Col.ZBottom));
			const double Water = WaterHeightAt(Bottom.X, Bottom.Y);
			if (Bottom.Z >= Water) continue;
			const double Len = Col.ZTop - Col.ZBottom;
			const double TopZ = Bottom.Z + Axis.Z * Len;
			const double F = Clamp((Water - Bottom.Z) / std::max(TopZ - Bottom.Z, 1e-6), 0.0, 1.0);
			const double Volume = Col.Area * Len * F;
			const Vec3 Point = Bottom + Axis * (0.5 * F * Len);
			const Vec3 PointVel = State.Velocity + OmegaWorld.Cross(Point - CGWorld);
			const double Wet = std::min(1.0, F * Len / 0.1);
			const double Damping = -C.HeaveDamping * Col.Area * Wet * PointVel.Z;
			AddWorldForce(Vec3(0.0, 0.0, kWaterDensity * kGravity * Volume + Damping), Point);
		}

		// Crew: the CG assumes them on the centerline; moving them out adds a gravity moment.
		{
			const Vec3 CrewWorld = Q.Rotate(Vec3(0.0, State.CrewOffset, 0.0));
			TorqueWorld += CrewWorld.Cross(Vec3(0.0, 0.0, -C.CrewMass * kGravity));
		}

		// Hull resistance (ITTC-57 friction + residuary by Froude number), applied along the hull's motion.
		const Vec3 HullPoint(-0.15, 0.0, -0.12);
		const Vec3 HullVel = Q.Unrotate(PointVelocityWorld(HullPoint));
		const double HeelAbs = std::fabs(Q.Heel());
		{
			const double U = HullVel.X;
			const double V = std::fabs(U);
			if (V > 1e-4)
			{
				const double Re = std::max(V * 0.7 * C.WaterlineLength / kWaterViscosity, 1e4);
				const double LogRe = std::log10(Re) - 2.0;
				const double Cf = 0.075 / (LogRe * LogRe);
				const double Friction = 0.5 * kWaterDensity * V * V * C.WettedArea * Cf * C.FormFactor * (1.0 + 0.4 * std::sin(HeelAbs));
				const double Froude = V / std::sqrt(kGravity * C.WaterlineLength);
				const double Residuary = Mass * kGravity * ResistanceCoefficient(Froude) * (1.0 + 2.0 * std::sin(HeelAbs) * std::sin(HeelAbs));
				// Chop: from the wind at the boat (waves come from where the wind comes from).
				const Vec3 WindHere = Wind.VelocityAt(Vec3(CGWorld.X, CGWorld.Y, 10.0), State.Time);
				const double Tws = WindHere.LengthXY() / (10.0 * kKnot);
				const double IntoWaves = Tws > 1e-6 ? -WindHere.Dot(Q.Forward()) / WindHere.LengthXY() : 0.0; // cos TWA
				const double Chop = Mass * kGravity * C.ChopResistance * Tws * Tws * Tws * (1.0 + IntoWaves) * (1.0 + IntoWaves) * 0.25 * Clamp(V / 2.0, 0.0, 1.0);
				AddBodyForce(Vec3(-Sign(U) * (Friction + Residuary + Chop), 0.0, 0.0), HullPoint);
			}
			// Cross-flow drag at two stations: sway resistance and yaw damping at low speed.
			for (double StationX : { 1.9, -1.9 })
			{
				const Vec3 P(StationX, 0.0, -0.12);
				const double VY = Q.Unrotate(PointVelocityWorld(P)).Y;
				AddBodyForce(Vec3(0.0, -0.5 * kWaterDensity * C.HullLateralCd * C.HullLateralArea * VY * std::fabs(VY), 0.0), P);
			}
			// Munk moment: the canoe body wants to turn broadside to its motion (part of weather helm).
			const Vec3 CGVelBody = Q.Unrotate(State.Velocity);
			TorqueBody.Z += -C.MunkAddedMass * CGVelBody.X * CGVelBody.Y;
			TorqueBody.Z += -C.YawDampingLinear * State.AngularVelocity.Z;
			TorqueBody.X += -C.ExtraRollDamping * State.AngularVelocity.X;
		}

		// Keel and rudder.
		double RudderLift = 0.0, RudderQA = 0.0;
		{
			const Vec3 KeelFlow = -Q.Unrotate(PointVelocityWorld(C.Keel.Center));
			const double KeelFactor = 1.0 - 0.9 * SmoothStep(60.0 * kDegToRad, 85.0 * kDegToRad, HeelAbs);
			const FFoilResult K = ComputeFoil(C.Keel, KeelFlow, Vec3(-1, 0, 0), kWaterDensity, KeelFactor);
			AddBodyForce(K.Force, C.Keel.Center);

			// The rudder sits in the keel's wake: the keel turns the flow by its downwash angle, so the rudder sees
			// less leeway than the keel does. That is why a boat carries weather helm with the tiller to windward.
			Vec3 RudderFlow = -Q.Unrotate(PointVelocityWorld(C.Rudder.Center));
			const double Downwash = C.KeelDownwashFactor * 2.0 * K.LiftCoefficient / (kPi * C.Keel.EffectiveAspectRatio);
			{
				const double Cs = std::cos(-Downwash), Sn = std::sin(-Downwash);
				RudderFlow = Vec3(RudderFlow.X * Cs - RudderFlow.Y * Sn, RudderFlow.X * Sn + RudderFlow.Y * Cs, RudderFlow.Z);
			}
			const double RudderFactor = 1.0 - 0.8 * SmoothStep(30.0 * kDegToRad, 55.0 * kDegToRad, HeelAbs); // ventilation
			const Vec3 Chord(-std::cos(State.RudderAngle), std::sin(State.RudderAngle), 0.0);
			const FFoilResult R = ComputeFoil(C.Rudder, RudderFlow, Chord, kWaterDensity, RudderFactor);
			AddBodyForce(R.Force, C.Rudder.Center);
			const double Speed = Vec3(RudderFlow.X, RudderFlow.Y, 0.0).Length();
			RudderQA = 0.5 * kWaterDensity * Speed * Speed * C.Rudder.Area;
			RudderLift = R.LiftCoefficient;
		}

		// Sails and windage.
		ComputeSails(Dt, Controls, Wind, ForceBody, TorqueBody);

		// Combine and integrate (semi-implicit Euler). Added mass and inertia act along body axes.
		ForceWorld += Q.Rotate(ForceBody);
		const Vec3 TorqueTotalBody = Q.Unrotate(TorqueWorld) + TorqueBody;
		const Vec3 AccelBody = Q.Unrotate(ForceWorld).Div(EffectiveMass);
		State.Velocity += Q.Rotate(AccelBody) * Dt;

		const Vec3& W = State.AngularVelocity;
		const Vec3 Gyro = W.Cross(Inertia.Mul(W));
		State.AngularVelocity += (TorqueTotalBody - Gyro).Div(EffectiveInertia) * Dt;

		State.Position += State.Velocity * Dt;
		const Vec3& W2 = State.AngularVelocity;
		const Quat Spin = State.Orientation * Quat(W2.X, W2.Y, W2.Z, 0.0);
		State.Orientation = Quat(
			State.Orientation.X + 0.5 * Spin.X * Dt, State.Orientation.Y + 0.5 * Spin.Y * Dt,
			State.Orientation.Z + 0.5 * Spin.Z * Dt, State.Orientation.W + 0.5 * Spin.W * Dt).Normalized();

		// Rudder: the helm holds the tiller with finite stiffness, so the rudder's hinge moment pushes it
		// toward streaming with the flow. That offset is the weather (or lee) helm you feel.
		const double Hinge = RudderLift * RudderQA * C.RudderStockToCP;
		const double Commanded = Clamp(Controls.Tiller, -1.0, 1.0) * C.MaxRudderAngleDeg * kDegToRad;
		const double RudderTarget = Clamp(Commanded - Hinge / C.HelmStiffness, -C.MaxRudderAngleDeg * kDegToRad, C.MaxRudderAngleDeg * kDegToRad);
		State.RudderAngle += (RudderTarget - State.RudderAngle) * std::min(1.0, Dt / C.RudderResponseTime);

		// Crew move to the windward side, sitting or hiking.
		const double Hike = Clamp(Controls.Hike, -1.0, 1.0);
		const double Target = State.WindwardSide * (Hike >= 0.0 ? C.CrewSitOut + C.CrewHikeOut * Hike : C.CrewSitOut * (1.0 + 2.0 * Hike));
		State.CrewOffset = MoveToward(State.CrewOffset, Target, C.CrewMoveSpeed * Dt);

		State.Time += Dt;

		// Telemetry.
		FBoatTelemetry& T = Telemetry;
		const Vec3 VelBody = Q.Unrotate(State.Velocity);
		T.BoatSpeed = State.Velocity.LengthXY();
		T.ForwardSpeed = VelBody.X;
		T.Heading = Q.Heading();
		T.Heel = Q.Heel();
		T.Pitch = Q.Pitch();
		T.Leeway = T.BoatSpeed > 0.2 ? WrapAngle(std::atan2(State.Velocity.Y, State.Velocity.X) - T.Heading) : 0.0;
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

		// Windward side with hysteresis, from the apparent wind at the masthead.
		if (std::fabs(T.ApparentWindAngle) > 15.0 * kDegToRad && std::fabs(T.ApparentWindAngle) < 165.0 * kDegToRad)
		{
			State.WindwardSide = T.ApparentWindAngle > 0.0 ? 1 : -1;
		}
	}

	void FBoatModel::ComputeSails(double Dt, const FBoatControls& Controls, const FWindField& Wind, Vec3& ForceBody, Vec3& TorqueBody)
	{
		const FBoatConfig& C = Config;
		const Quat& Q = State.Orientation;
		FBoatTelemetry& T = Telemetry;
		T.NumMainStrips = C.Main.NumStrips;
		T.NumJibStrips = C.Jib.NumStrips;
		T.DriveForce = 0.0;
		T.HeelingForce = 0.0;

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
		const double JibAWA = MeanAngle(C.Jib);
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
		// Wing-on-wing: deep enough downwind, the jib can be held out on the side opposite the main.
		const bool bWing = Controls.bWingOnWing && std::fabs(JibAWA) > 150.0 * kDegToRad;
		if (bWing)
		{
			State.JibSide = -State.MainSide;
		}

		// Shape from the controls.
		const double MainSheet = Clamp(Controls.MainSheet, 0.0, 1.0);
		const double JibSheet = Clamp(Controls.JibSheet, 0.0, 1.0);
		const double Vang = Clamp(Controls.Vang, 0.0, 1.0);
		const double Cunningham = Clamp(Controls.Cunningham, 0.0, 1.0);
		const double Outhaul = Clamp(Controls.Outhaul, 0.0, 1.0);
		const double Backstay = Clamp(Controls.Backstay, 0.0, 1.0);

		const double LeechTension = std::max(Vang, Clamp(1.0 - MainSheet / 0.3, 0.0, 1.0));
		const double MainTwist = (2.0 + 20.0 * (1.0 - LeechTension) + 4.0 * Backstay) * kDegToRad;
		const double JibTwist = (5.0 + 10.0 * JibSheet) * kDegToRad;

		auto Camber = [&](bool bMain, double H)
		{
			double Value;
			if (bMain)
			{
				Value = C.Main.BaseCamber + 0.01 - 0.02 * H - Outhaul * 0.05 * (1.0 - H) * (1.0 - H) - Cunningham * 0.015 - Backstay * 0.04 * H;
			}
			else
			{
				Value = C.Jib.BaseCamber - Backstay * 0.03 + 0.02 * JibSheet;
			}
			return Clamp(Value, 0.04, 0.18);
		};

		// The sheet limits how far the sail can go out; the wind pushes it out to that limit or until it
		// lines up with the flow and luffs.
		auto NaturalAngle = [&](double AWA, double MeanTwist, double LuffAlpha)
		{
			return std::fabs(AWA) - MeanTwist - LuffAlpha + 2.0 * kDegToRad;
		};
		const double MainLuff = -(0.4 * Camber(true, 0.5) + 0.035);
		const double JibLuff = -(0.4 * Camber(false, 0.5) + 0.035);
		const double TravelerAngle = Clamp(Controls.Traveler, -1.0, 1.0) * 8.0 * kDegToRad;
		const double MainLimit = std::max(TravelerAngle + MainSheet * 85.0 * kDegToRad, -4.0 * kDegToRad);
		const double JibLimit = (8.0 + JibSheet * 72.0) * kDegToRad;
		const double MainTarget = Clamp(std::min(MainLimit, NaturalAngle(MainAWA, 0.5 * MainTwist, MainLuff)), -4.0 * kDegToRad, 85.0 * kDegToRad);
		const double JibTarget = bWing ? std::min(JibLimit, 80.0 * kDegToRad)
			: Clamp(std::min(JibLimit, NaturalAngle(JibAWA, 0.5 * JibTwist, JibLuff)), 0.0, 80.0 * kDegToRad);

		State.BoomAngle = MoveToward(State.BoomAngle, State.MainSide * MainTarget, 150.0 * kDegToRad * Dt);
		State.JibAngle = MoveToward(State.JibAngle, State.JibSide * JibTarget, 200.0 * kDegToRad * Dt);

		// Blanketing: running, the jib sits in the main's wind shadow.
		const double Blanket = bWing ? 1.0 : 1.0 - 0.35 * SmoothStep(140.0 * kDegToRad, 170.0 * kDegToRad, std::fabs(JibAWA));

		// Foot angle is measured from the centerline toward the sail's side; slightly negative means the boom is
		// pulled a little to windward of the centerline (traveler up in light air).
		auto DoSail = [&](bool bMain, const FSailGeometry& Geo, int Side, double FootAngleSigned, double Twist, double StallDelta,
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
				S.Camber = Camber(bMain, H);
				const double Angle = std::min(Foot + S.TwistFromFoot, 95.0 * kDegToRad);
				S.AngleFromCenterline = Side * Angle;
				const Vec3 Chord = SailChordDir(Angle, Side);
				S.CenterOfEffort = Vec3(G.LuffX, 0.0, 0.5 * (G.ZBottom + G.ZTop)) + Chord * (0.42 * G.Chord);

				const Vec3 Air = Apparent(S.CenterOfEffort) * WindScale;
				const Vec3 U(Air.X, Air.Y, 0.0);
				const double Speed = U.Length();
				S.ApparentSpeed = Speed;
				S.ApparentAngle = AngleFrom(Air);
				if (Speed < 1e-3)
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

				const double Q2 = 0.5 * kAirDensity * Speed * Speed * G.Area;
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

		const double JibHeadZ = C.Jib.Strips[C.Jib.NumStrips - 1].ZTop;
		const double JibUpwash = 1.0 + 0.08 * Clamp(MainMeanLift / 1.4, 0.0, 1.0);
		const double JibCL = DoSail(false, C.Jib, State.JibSide, State.JibAngle, JibTwist, 0.0, 0.0, 0.0, JibUpwash, Blanket, T.JibStrips);
		const double Downwash = 0.05 * JibCL;
		MainMeanLift = DoSail(true, C.Main, State.MainSide, State.BoomAngle, MainTwist, Cunningham * 2.0 * kDegToRad, Downwash, JibHeadZ, 1.0, 1.0, T.MainStrips);

		// Windage of the mast, rigging, topsides and crew.
		for (const auto& [Point, CdA] : { std::pair<Vec3, double>(Vec3(C.MastX, 0.0, 4.0), C.RigWindageCdA), std::pair<Vec3, double>(Vec3(-0.5, 0.0, 0.8), C.HullWindageCdA) })
		{
			const Vec3 Air = Apparent(Point);
			const Vec3 U(Air.X, Air.Y, 0.0);
			const Vec3 F = U * (0.5 * kAirDensity * CdA * U.Length());
			ForceBody += F;
			TorqueBody += (Point - CenterOfGravity).Cross(F);
		}
	}
}
