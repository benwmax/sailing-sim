#include "Misc/AutomationTest.h"
#include "Cannons.h"

#include <algorithm>
#include <cmath>
#include <string>
#include <vector>

#if WITH_DEV_AUTOMATION_TESTS

// Cannon fire (docs/cannon-fire/): the frigate's gun table, the drill, the recoil, the smoke and the tuning table.

using namespace Sailing;

namespace
{
	constexpr EAutomationTestFlags CannonFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;
	constexpr double CannonDt = 1.0 / 60.0;

	FCannonParams NoMisfires()
	{
		FCannonParams P;
		P.MisfireChance = 0.0;
		return P;
	}

	/** Run the battery for Seconds; returns the shots that went off (not the flashes in the pan). */
	std::vector<FCannonShot> RunFor(FCannonBattery& B, double& T, double Seconds, const Vec3& Gravity = Vec3(0, 0, -9.81))
	{
		std::vector<FCannonShot> Out;
		const int32 Steps = FMath::RoundToInt(Seconds / CannonDt);
		for (int32 I = 0; I < Steps; ++I)
		{
			B.Step({ CannonDt, T, Gravity });
			for (const FCannonShot& S : B.Shots()) if (!S.bMisfire) Out.push_back(S);
			T += CannonDt;
		}
		return Out;
	}

	/** One gun of a kind on the starboard side. */
	std::vector<FCannonMount> OneGun(ECannonKind Kind)
	{
		for (const FCannonMount& M : FrigateCannonMounts())
		{
			if (M.Kind == Kind && M.Side == ECannonSide::Starboard) return { M };
		}
		return {};
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCannonTableTest, "SailingSim.Physics.Cannons.Table", CannonFlags)
bool FCannonTableTest::RunTest(const FString&)
{
	const std::vector<FCannonMount> Guns = FrigateCannonMounts();
	int32 Long[2] = { 0, 0 }, Carr[2] = { 0, 0 };
	for (const FCannonMount& M : Guns)
	{
		const int32 S = M.Side == ECannonSide::Starboard ? 1 : 0;
		(M.Kind == ECannonKind::Long24 ? Long : Carr)[S]++;
		const FString Id(M.Id);
		TestTrue(FString::Printf(TEXT("%s's axes are unit"), *Id), FMath::IsNearlyEqual(M.AxisX.Length(), 1.0, 1e-3)
			&& FMath::IsNearlyEqual(M.AxisY.Length(), 1.0, 1e-3) && FMath::IsNearlyEqual(M.AxisZ.Length(), 1.0, 1e-3));
		TestTrue(FString::Printf(TEXT("%s's axes are square"), *Id), FMath::Abs(M.AxisX.Dot(M.AxisZ)) < 1e-3 && FMath::Abs(M.AxisX.Dot(M.AxisY)) < 1e-3);
		// Out through the port: to starboard (+Y) on the starboard side.
		TestTrue(FString::Printf(TEXT("%s points out of her own side"), *Id), (M.Side == ECannonSide::Starboard ? 1.0 : -1.0) * M.AxisX.Y > 0.9);
		TestTrue(FString::Printf(TEXT("%s recoils inboard of her run-out place"), *Id), M.RunInX < M.RunOutX - 0.3);
		TestTrue(FString::Printf(TEXT("%s stands on her own side of the ship"), *Id), (M.Side == ECannonSide::Starboard ? 1.0 : -1.0) * M.Origin.Y > 3.0);
		if (M.Kind == ECannonKind::Long24) TestTrue(FString::Printf(TEXT("%s has a lid"), *Id), M.LidOpenDeg > 45.0);
	}
	TestEqual(TEXT("14 long 24-pounders a side"), Long[0] * 100 + Long[1], 1414);
	TestEqual(TEXT("11 carronades a side"), Carr[0] * 100 + Carr[1], 1111);
	// The muzzle stands outboard of the side (its port frame's origin) run out, and inboard run in.
	FCannonBattery B;
	B.SetParams(NoMisfires());
	B.Init(Guns, 1);
	B.MakeReady(ECannonSide::Both);
	for (const FGun& G : B.Guns())
	{
		const Vec3 Muzzle = G.BarrelToShip(B.Spec(G.Mount.Kind).Muzzle, B.Spec(G.Mount.Kind));
		const double Out = (Muzzle - G.Mount.Origin).Dot(G.Mount.AxisX);
		TestTrue(FString::Printf(TEXT("%hs's muzzle is outside the side run out (%.2f m)"), G.Mount.Id, Out), Out > 0.1);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCannonDrillTest, "SailingSim.Physics.Cannons.Drill", CannonFlags)
bool FCannonDrillTest::RunTest(const FString&)
{
	FCannonBattery B;
	B.SetParams(NoMisfires());
	B.Init(FrigateCannonMounts(), 1);
	double T = 0.0;
	// A broadside ordered from housed: the side casts loose, loads, opens its lids, runs out and fires together.
	B.Order(ECannonOrder::Fire, ECannonSide::Starboard, T);
	std::vector<FCannonShot> Shots = RunFor(B, T, 150.0);
	TestEqual(TEXT("every starboard gun fires once"), int32(Shots.size()), 25);
	double First = 1e9, Last = -1e9;
	for (const FCannonShot& S : Shots)
	{
		First = FMath::Min(First, S.Time);
		Last = FMath::Max(Last, S.Time);
		TestTrue(TEXT("only the starboard guns"), B.Guns()[size_t(S.Gun)].Mount.Side == ECannonSide::Starboard);
	}
	const FCannonParams& P = B.GetParams();
	TestTrue(FString::Printf(TEXT("together: within the broadside's spread and the locks' (%.2f s)"), Last - First),
		Last - First <= P.BroadsideSpreadS + 2.0 * P.LockSpreadS + 2.0 * CannonDt);
	TestTrue(FString::Printf(TEXT("cleared for action in 1-2 minutes (%.0f s)"), First), First > 60.0 && First < 120.0);
	for (const FGun& G : B.Guns())
	{
		if (G.Mount.Side == ECannonSide::Port) TestTrue(TEXT("the port guns stay housed"), G.State == EGunState::Housed && G.LidDeg == 0.0);
	}
	// They reload and run out again, then wait for the next word.
	RunFor(B, T, 90.0);
	const FCannonSideStatus Ready = B.Status(ECannonSide::Starboard);
	TestEqual(TEXT("reloaded and run out for the next broadside"), Ready.Ready, 25);
	// At will: about a round a minute from each gun (the 1812 drill), the carronades a little quicker.
	B.SetFireMode(ECannonFireMode::AtWill);
	B.Order(ECannonOrder::Fire, ECannonSide::Starboard, T);
	const int32 AtWill = int32(RunFor(B, T, 600.0).size());
	const double PerMinute = double(AtWill) / 25.0 / 10.0;
	TestTrue(FString::Printf(TEXT("at will: %.2f rounds a minute a gun"), PerMinute), PerMinute > 0.8 && PerMinute < 1.4);
	// Cease fire: nothing more goes off once the guns in their locks have.
	B.Order(ECannonOrder::CeaseFire, ECannonSide::Starboard, T);
	RunFor(B, T, 1.0);
	TestEqual(TEXT("cease fire"), int32(RunFor(B, T, 120.0).size()), 0);
	// Secure: every gun housed again, its lid shut.
	B.Order(ECannonOrder::Secure, ECannonSide::Starboard, T);
	RunFor(B, T, 200.0);
	for (const FGun& G : B.Guns())
	{
		TestTrue(FString::Printf(TEXT("%hs secured"), G.Mount.Id), G.State == EGunState::Housed && G.LidDeg == 0.0);
		if (G.Mount.Kind == ECannonKind::Long24) TestTrue(TEXT("housed against the sill"), FMath::IsNearlyEqual(G.X, G.Mount.HousedX, 1e-6));
	}
	// A ripple goes from forward aft, an interval apart.
	FCannonBattery R;
	R.SetParams(NoMisfires());
	R.Init(FrigateCannonMounts(), 2);
	R.MakeReady(ECannonSide::Port);
	R.SetFireMode(ECannonFireMode::Ripple);
	double T2 = 0.0;
	R.Order(ECannonOrder::Fire, ECannonSide::Port, T2);
	const std::vector<FCannonShot> Ripple = RunFor(R, T2, 20.0);
	TestEqual(TEXT("the ripple fires every port gun"), int32(Ripple.size()), 25);
	bool bForwardFirst = true;
	for (size_t I = 1; I < Ripple.size(); ++I)
	{
		const double XA = R.Guns()[size_t(Ripple[I - 1].Gun)].Mount.Origin.X, XB = R.Guns()[size_t(Ripple[I].Gun)].Mount.Origin.X;
		if (XB > XA + 1.0 && Ripple[I].Time - Ripple[I - 1].Time > 2.0 * R.GetParams().LockSpreadS + 1e-6) bForwardFirst = false;
	}
	TestTrue(TEXT("the ripple runs from forward aft"), bForwardFirst);
	// Determinism: the same seed, the same shots at the same times.
	FCannonBattery A1, A2;
	A1.Init(FrigateCannonMounts(), 9);
	A2.Init(FrigateCannonMounts(), 9);
	A1.SetFireMode(ECannonFireMode::AtWill);
	A2.SetFireMode(ECannonFireMode::AtWill);
	double Ta = 0.0, Tb = 0.0;
	A1.Order(ECannonOrder::Fire, ECannonSide::Both, 0.0);
	A2.Order(ECannonOrder::Fire, ECannonSide::Both, 0.0);
	const std::vector<FCannonShot> Sa = RunFor(A1, Ta, 240.0), Sb = RunFor(A2, Tb, 240.0);
	bool bSame = Sa.size() == Sb.size();
	for (size_t I = 0; bSame && I < Sa.size(); ++I) bSame = Sa[I].Gun == Sb[I].Gun && Sa[I].Time == Sb[I].Time;
	TestTrue(TEXT("deterministic for a seed"), bSame && !Sa.empty());
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCannonRecoilTest, "SailingSim.Physics.Cannons.Recoil", CannonFlags)
bool FCannonRecoilTest::RunTest(const FString&)
{
	for (const ECannonKind Kind : { ECannonKind::Long24, ECannonKind::Carronade32 })
	{
		const TCHAR* Name = Kind == ECannonKind::Long24 ? TEXT("long 24") : TEXT("carronade");
		for (const double HeelDeg : { -10.0, 0.0, 10.0 })
		{
			FCannonBattery B;
			B.SetParams(NoMisfires());
			B.Init(OneGun(Kind), 3);
			B.MakeReady(ECannonSide::Starboard);
			// Heeled to port (+), the starboard side is up: a starboard gun recoils downhill.
			const double H = FMath::DegreesToRadians(HeelDeg);
			const Vec3 Gravity(0.0, -9.81 * FMath::Sin(H), -9.81 * FMath::Cos(H));
			double T = 0.0;
			B.Order(ECannonOrder::Fire, ECannonSide::Starboard, T);
			Vec3 Kick;
			double Peak = 0.0;
			bool bFired = false;
			int32 Steps = 0;
			for (; Steps < 600; ++Steps)
			{
				B.Step({ CannonDt, T, Gravity });
				bFired = bFired || !B.Shots().empty();
				const FGun& G = B.Guns()[0];
				Peak = FMath::Max(Peak, G.Mount.RunOutX - G.X);
				Kick += B.ForceOnShip() * CannonDt;
				T += CannonDt;
				if (bFired && G.State == EGunState::Spent) break;
			}
			const FGun& G = B.Guns()[0];
			const double Run = G.Mount.RunOutX - G.Mount.RunInX;
			TestTrue(FString::Printf(TEXT("%s at %.0f deg heel fired and came to rest"), Name, HeelDeg), bFired && G.State == EGunState::Spent);
			// Level or downhill she flies in to the breeching and stretches it no more than its give (plus a margin); uphill
			// the slope may stop her short.
			const double Give = B.GetParams().BreechingStretchM;
			if (HeelDeg >= 0.0)
			{
				TestTrue(FString::Printf(TEXT("%s at %.0f deg: recoils to the breeching (%.2f of %.2f m)"), Name, HeelDeg, Peak, Run),
					Peak > Run - 0.02 && Peak < Run + 1.5 * Give);
			}
			else
			{
				TestTrue(FString::Printf(TEXT("%s at %.0f deg: recoils most of the way (%.2f of %.2f m)"), Name, HeelDeg, Peak, Run),
					Peak > 0.6 * Run && Peak < Run + 1.5 * Give);
			}
			TestTrue(FString::Printf(TEXT("%s at %.0f deg: the train tackle holds her where she stopped"), Name, HeelDeg),
				FMath::Abs((G.Mount.RunOutX - G.X) - Peak) < 0.02);
			// The ship takes the shot's and gas's momentum, pushed inboard (to port, for a starboard gun), level.
			if (HeelDeg == 0.0)
			{
				const double I = B.RecoilImpulse(Kind);
				TestTrue(FString::Printf(TEXT("%s: the ship takes the recoil's impulse (%.0f of %.0f N s)"), Name, Kick.Length(), I),
					FMath::Abs(Kick.Length() - I) < 0.05 * I);
				TestTrue(FString::Printf(TEXT("%s: pushed inboard"), Name), Kick.Y < -0.9 * Kick.Length());
			}
		}
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCannonSmokeTest, "SailingSim.Physics.Cannons.Smoke", CannonFlags)
bool FCannonSmokeTest::RunTest(const FString&)
{
	FCannonParams P = NoMisfires();
	auto Broadside = [&](int32 Budget, double Seconds, double WindMs, double& OutMass, std::vector<FSmokePuff>& OutPuffs, int32& OutMerges)
	{
		FCannonBattery B;
		B.SetParams(P);
		B.Init(FrigateCannonMounts(), 1);
		B.MakeReady(ECannonSide::Starboard);
		B.Order(ECannonOrder::Fire, ECannonSide::Starboard, 0.0);
		FCannonSmoke Smoke;
		Smoke.SetParams(P);
		Smoke.SetBudget(Budget);
		FSteadyCannonWorld W;
		W.Wind = Vec3(0.0, WindMs, 0.0);
		double T = 0.0, Emitted = 0.0;
		for (int32 I = 0; I < FMath::RoundToInt(Seconds / CannonDt); ++I)
		{
			B.Step({ CannonDt, T, Vec3(0, 0, -9.81) });
			for (const FCannonShot& S : B.Shots())
			{
				const FGun& G = B.Guns()[size_t(S.Gun)];
				const FCannonKindSpec& K = B.Spec(G.Mount.Kind);
				Smoke.EmitShot(S.MuzzleShip, S.BoreShip, G.BarrelToShip(K.Vent, K), Vec3(), S.ChargeKg, S.bMisfire, T, G.Mount.Kind == ECannonKind::Long24);
				Emitted += S.ChargeKg * P.SmokePerChargeKg * 1.03;
			}
			Smoke.Step(CannonDt, T, W);
			for (const FSmokePuff& Puff : Smoke.Puffs())
			{
				if (Puff.P.Z < W.Water) { OutMerges = -1; return Emitted; }   // under the water: fail below
			}
			T += CannonDt;
		}
		OutMass = Smoke.TotalMass();
		OutPuffs = Smoke.Puffs();
		OutMerges = Smoke.Merges();
		return Emitted;
	};
	double Mass = 0.0;
	std::vector<FSmokePuff> Puffs;
	int32 Merges = 0;
	const double Emitted = Broadside(4096, 10.0, 5.0, Mass, Puffs, Merges);
	TestTrue(TEXT("no smoke under the water"), Merges >= 0);
	TestTrue(FString::Printf(TEXT("a broadside's smoke is all there at 10 s (%.1f of %.1f kg)"), Mass, Emitted), FMath::Abs(Mass - Emitted) < 0.02 * Emitted);
	// The blast throws the plume out from her side, and the wind carries it on to leeward (starboard: +Y).
	double MeanY = 0.0, MaxOpacity = 0.0;
	for (const FSmokePuff& S : Puffs) { MeanY += S.P.Y * S.MassKg; MaxOpacity = FMath::Max(MaxOpacity, S.Opacity(P)); }
	MeanY /= FMath::Max(Mass, 1e-9);
	TestTrue(FString::Printf(TEXT("downwind of her side at 10 s (%.0f m)"), MeanY), MeanY > 30.0 && MeanY < 120.0);
	TestTrue(FString::Printf(TEXT("still thick at 10 s (%.2f)"), MaxOpacity), MaxOpacity > 0.3);
	// A minute on it has spread and thinned.
	double Mass60 = 0.0;
	std::vector<FSmokePuff> Late;
	Broadside(4096, 60.0, 5.0, Mass60, Late, Merges);
	double Late60 = 0.0;
	for (const FSmokePuff& S : Late) Late60 = FMath::Max(Late60, S.Opacity(P));
	TestTrue(FString::Printf(TEXT("thinned by a minute (%.2f, was %.2f)"), Late60, MaxOpacity), Late60 < 0.5 * MaxOpacity);
	// Over a small budget the oldest puffs merge: fewer puffs, the same smoke.
	double MassSmall = 0.0;
	std::vector<FSmokePuff> Small;
	int32 MergesSmall = 0;
	Broadside(128, 10.0, 5.0, MassSmall, Small, MergesSmall);
	TestTrue(FString::Printf(TEXT("held to its budget (%d)"), int32(Small.size())), Small.size() <= 128 && MergesSmall > 0);
	TestTrue(FString::Printf(TEXT("merging keeps the smoke (%.1f of %.1f kg)"), MassSmall, Mass), FMath::Abs(MassSmall - Mass) < 0.01 * Mass);
	// A flash's flame peaks at once and is gone within its life.
	FCannonFlash F;
	F.Start = 1.0;
	F.Life = P.FlashS;
	TestTrue(TEXT("the flash peaks early"), F.Intensity(1.0 + 0.06 * P.FlashS) > 0.99 && F.Intensity(1.0 + 0.5 * P.FlashS) < 0.5);
	TestEqual(TEXT("the flash is gone after its life"), F.Intensity(1.0 + 1.01 * P.FlashS), 0.0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCannonParamsTest, "SailingSim.Physics.Cannons.Params", CannonFlags)
bool FCannonParamsTest::RunTest(const FString&)
{
	FCannonParams P;
	double V = 0.0;
	TestTrue(TEXT("set by name, any case"), P.Set("jetspeedms", 90.0) && P.Get("JetSpeedMs", V) && V == 90.0);
	TestTrue(TEXT("integers round"), P.Set("PuffsLong", 24.6) && P.PuffsLong == 25);
	TestFalse(TEXT("unknown names refused"), P.Set("NoSuchKnob", 1.0));
	std::string Unknown;
	const int32 Applied = P.ApplyOverrides("FlashS=0.1, SmokeExtinction = 800 # thicker\nBogus=3\n# a comment\nCrewTimeScale=0.5", &Unknown);
	TestEqual(TEXT("overrides applied"), Applied, 3);
	TestEqual(TEXT("unknown keys listed"), FString(Unknown.c_str()), FString(TEXT("Bogus")));
	TestTrue(TEXT("override values"), P.FlashS == 0.1 && P.SmokeExtinction == 800.0 && P.CrewTimeScale == 0.5);
	// The dump reads back as the same parameters.
	FCannonParams Q;
	TestEqual(TEXT("the dump applies every parameter"), Q.ApplyOverrides(P.Dump()), int32(FCannonParams::Names().size()));
	TestTrue(TEXT("and reads back the same"), Q.FlashS == P.FlashS && Q.SmokeExtinction == P.SmokeExtinction && Q.PuffsLong == P.PuffsLong);
	return true;
}

#endif
