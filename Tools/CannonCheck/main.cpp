// Cannon fire, standalone (docs/cannon-fire/): the frigate's drill, recoil, smoke and flash without Unreal, in a second.
// scripts/cannon-check.sh [--drill | --recoil | --smoke [seconds] | --params | --budget <n>] [--fx "Key=V,..."]
// --smoke writes Artifacts/cannon-smoke.csv (time, puffs, mass, mean sigma, plume reach downwind, height) and
// Artifacts/cannon-puffs.csv (every puff at the end) for Tools/CannonCheck/plot_smoke.py.
#include "Cannons.h"

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <algorithm>
#include <string>

using namespace Sailing;

namespace
{
	FCannonParams Params;

	int RunDrill()
	{
		FCannonBattery B;
		B.SetParams(Params);
		B.Init(FrigateCannonMounts(), 1);
		B.SetFireMode(ECannonFireMode::Broadside);
		const double Dt = 1.0 / 60.0;
		double T = 0.0;
		B.Order(ECannonOrder::Fire, ECannonSide::Starboard, T);
		int Shots = 0;
		double First = -1, Last = -1;
		std::printf("Broadside from housed, starboard (%d guns a side):\n", B.Status(ECannonSide::Starboard).Guns);
		for (int I = 0; I < int(400.0 / Dt); ++I)
		{
			B.Step({ Dt, T, Vec3(0, 0, -9.81) });
			for (const FCannonShot& S : B.Shots())
			{
				if (S.bMisfire) { std::printf("  %6.2f s  %s flash in the pan\n", T, B.Guns()[size_t(S.Gun)].Mount.Id); continue; }
				if (First < 0) First = T;
				Last = T;
				++Shots;
			}
			if (Shots && Last >= 0 && T - Last > 5.0 && Shots >= 25) break;
			if (I % int(20.0 / Dt) == 0)
			{
				const FCannonSideStatus St = B.Status(ECannonSide::Starboard);
				std::printf("  %6.1f s  ready %2d  loaded %2d  next ready %.1f s  shots %d\n", T, St.Ready, St.Loaded, St.NextReadyS, St.Shots);
			}
			T += Dt;
		}
		std::printf("  first shot %.2f s, last %.2f s: %d shots over %.2f s\n", First, Last, Shots, Last - First);
		// Rate of fire at will.
		B.SetFireMode(ECannonFireMode::AtWill);
		B.Order(ECannonOrder::Fire, ECannonSide::Starboard, T);
		int Will = 0;
		for (int I = 0; I < int(600.0 / Dt); ++I) { B.Step({ Dt, T, Vec3(0, 0, -9.81) }); for (const FCannonShot& S : B.Shots()) Will += S.bMisfire ? 0 : 1; T += Dt; }
		std::printf("At will for 10 min: %d shots from %d guns: %.2f rounds a minute a gun\n", Will, 25, double(Will) / 25.0 / 10.0);
		B.Order(ECannonOrder::Secure, ECannonSide::Starboard, T);
		for (int I = 0; I < int(300.0 / Dt); ++I) { B.Step({ Dt, T, Vec3(0, 0, -9.81) }); T += Dt; }
		std::printf("Secured: housed %d of %d\n", B.Status(ECannonSide::Starboard).ByState[int(EGunState::Housed)], B.Status(ECannonSide::Starboard).Guns);
		return 0;
	}

	int RunRecoil()
	{
		for (int Heel = -10; Heel <= 10; Heel += 5)
		{
			for (int Kind = 0; Kind < 2; ++Kind)
			{
				FCannonBattery B;
				FCannonParams P = Params;
				P.MisfireChance = 0.0;
				B.SetParams(P);
				std::vector<FCannonMount> All = FrigateCannonMounts(), One;
				for (const FCannonMount& M : All) if (M.Side == ECannonSide::Starboard && int(M.Kind) == Kind) { One.push_back(M); break; }
				B.Init(One, 3);
				B.MakeReady(ECannonSide::Starboard);
				// Heel to port (positive heel, starboard side up) puts the starboard guns uphill: gravity along -Y in the ship frame...
				const double H = Heel * 3.14159265358979 / 180.0;
				const Vec3 G(0.0, -9.81 * std::sin(H), -9.81 * std::cos(H));
				const double Dt = 1.0 / 120.0;
				double T = 0.0, Peak = 0.0, MaxF = 0.0;
				Vec3 Impulse;
				B.Order(ECannonOrder::Fire, ECannonSide::Starboard, 0.0);
				double Fired = -1, Stopped = -1;
				for (int I = 0; I < 1200; ++I)
				{
					B.Step({ Dt, T, G });
					if (!B.Shots().empty() && Fired < 0) Fired = T;
					const FGun& Gun = B.Guns()[0];
					if (Fired >= 0) Peak = std::max(Peak, Gun.Mount.RunOutX - Gun.X);
					Impulse += B.ForceOnShip() * Dt;
					MaxF = std::max(MaxF, B.ForceOnShip().Length());
					if (Fired >= 0 && Stopped < 0 && Gun.State == EGunState::Spent) Stopped = T;
					T += Dt;
				}
				const FGun& Gun = B.Guns()[0];
				std::printf("%-11s heel %+3d deg: v0 %.2f m/s, recoil %.2f m (breeching taut at %.2f), stopped in %.2f s, rests %.2f m in; "
					"impulse on ship %.0f N s (shot+gas %.0f), peak force %.0f kN\n",
					Kind == 0 ? "long 24" : "carronade", Heel, B.RecoilImpulse(Gun.Mount.Kind) / B.Spec(Gun.Mount.Kind).RecoilingKg(), Peak,
					Gun.Mount.RunOutX - Gun.Mount.RunInX, Stopped - Fired, Gun.Mount.RunOutX - Gun.X, Impulse.Length(), B.RecoilImpulse(Gun.Mount.Kind), MaxF / 1000.0);
			}
		}
		return 0;
	}

	int RunSmoke(double Seconds, int Budget, double WindMs)
	{
		FCannonBattery B;
		B.SetParams(Params);
		B.Init(FrigateCannonMounts(), 1);
		B.MakeReady(ECannonSide::Starboard);
		B.Order(ECannonOrder::Fire, ECannonSide::Starboard, 0.0);
		FCannonSmoke Smoke;
		Smoke.SetParams(Params);
		Smoke.SetBudget(Budget);
		FSteadyCannonWorld W;
		W.Wind = Vec3(0.0, WindMs, 0.0);   // blowing toward starboard: the smoke goes off to leeward, away from her
		const double Dt = 1.0 / 60.0;
		FILE* Csv = std::fopen("Artifacts/cannon-smoke.csv", "w");
		if (Csv) std::fprintf(Csv, "t,puffs,mass_kg,mean_sigma_m,reach_m,top_m,merges,flashes,sparks\n");
		double T = 0.0;
		for (int I = 0; I < int(Seconds / Dt); ++I)
		{
			B.Step({ Dt, T, Vec3(0, 0, -9.81) });
			for (const FCannonShot& S : B.Shots())
			{
				const FGun& G = B.Guns()[size_t(S.Gun)];
				const Vec3 Vent = G.BarrelToShip(B.Spec(G.Mount.Kind).Vent, B.Spec(G.Mount.Kind));
				Smoke.EmitShot(S.MuzzleShip + Vec3(0, 0, 3.0), S.BoreShip, Vent + Vec3(0, 0, 3.0), Vec3(), S.ChargeKg, S.bMisfire, T,
					G.Mount.Kind == ECannonKind::Long24);
			}
			Smoke.Step(Dt, T, W);
			if (Csv && I % 6 == 0)
			{
				double Sig = 0, Reach = 0, Top = 0;
				for (const FSmokePuff& P : Smoke.Puffs()) { Sig += P.Sigma; Reach = std::max(Reach, P.P.Y); Top = std::max(Top, P.P.Z + P.Sigma); }
				const size_t N = Smoke.Puffs().size();
				std::fprintf(Csv, "%.2f,%zu,%.3f,%.2f,%.1f,%.1f,%d,%zu,%zu\n", T, N, Smoke.TotalMass(), N ? Sig / double(N) : 0.0, Reach, Top,
					Smoke.Merges(), Smoke.Flashes().size(), Smoke.Sparks().size());
			}
			T += Dt;
		}
		if (Csv) std::fclose(Csv);
		FILE* Puffs = std::fopen("Artifacts/cannon-puffs.csv", "w");
		if (Puffs)
		{
			std::fprintf(Puffs, "x,y,z,sigma,mass_kg,opacity,age\n");
			for (const FSmokePuff& P : Smoke.Puffs())
				std::fprintf(Puffs, "%.2f,%.2f,%.2f,%.2f,%.4f,%.3f,%.1f\n", P.P.X, P.P.Y, P.P.Z, P.Sigma, P.MassKg, P.Opacity(Params), P.Age);
			std::fclose(Puffs);
		}
		double Op = 0.0;
		for (const FSmokePuff& P : Smoke.Puffs()) Op = std::max(Op, P.Opacity(Params));
		std::printf("Smoke after %.0f s in %.1f m/s: %zu puffs (budget %d, %d merges), %.2f kg, densest puff %.2f\n", Seconds, WindMs,
			Smoke.Puffs().size(), Budget, Smoke.Merges(), Smoke.TotalMass(), Op);
		return 0;
	}
}

int main(int Argc, char** Argv)
{
	std::string Mode = "--drill";
	double Seconds = 30.0, Wind = 5.0;
	int Budget = 1536;
	for (int I = 1; I < Argc; ++I)
	{
		const std::string A = Argv[I];
		if (A == "--fx" && I + 1 < Argc)
		{
			std::string Unknown;
			Params.ApplyOverrides(Argv[++I], &Unknown);
			if (!Unknown.empty()) { std::fprintf(stderr, "unknown: %s\n", Unknown.c_str()); return 2; }
		}
		else if (A == "--budget" && I + 1 < Argc) Budget = std::atoi(Argv[++I]);
		else if (A == "--wind" && I + 1 < Argc) Wind = std::atof(Argv[++I]);
		else if (A == "--smoke") { Mode = A; if (I + 1 < Argc && Argv[I + 1][0] != '-') Seconds = std::atof(Argv[++I]); }
		else Mode = A;
	}
	if (Mode == "--params") { std::printf("%s", Params.Dump().c_str()); return 0; }
	if (Mode == "--recoil") return RunRecoil();
	if (Mode == "--smoke") return RunSmoke(Seconds, Budget, Wind);
	return RunDrill();
}
