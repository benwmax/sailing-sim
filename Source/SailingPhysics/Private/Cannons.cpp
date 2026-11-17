#include "Cannons.h"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstdio>
#include <cstdlib>

namespace Sailing
{
	namespace
	{
		constexpr double kG = 9.81;
		constexpr double kInch = 0.0254;
		constexpr double kTwoPi = 2.0 * 3.14159265358979323846;
		// The long 24-pounder's service charge, the scale the blast's jet and flame are set for.
		constexpr double kLongChargeKg = 3.63;

		int32_t SideIndex(ECannonSide S) { return S == ECannonSide::Starboard ? 1 : 0; }

		double SmoothStep01(double T)
		{
			const double X = Clamp(T, 0.0, 1.0);
			return X * X * (3.0 - 2.0 * X);
		}

		std::string Lower(std::string S)
		{
			for (char& C : S) C = char(std::tolower(static_cast<unsigned char>(C)));
			return S;
		}

		std::string Trim(const std::string& S)
		{
			size_t A = 0, B = S.size();
			while (A < B && std::isspace(static_cast<unsigned char>(S[A]))) ++A;
			while (B > A && std::isspace(static_cast<unsigned char>(S[B - 1]))) --B;
			return S.substr(A, B - A);
		}

		/** The tuning table: every parameter by name, with its line for the dump. */
		struct FParamRow
		{
			const char* Name;
			double FCannonParams::* D;
			int32_t FCannonParams::* I;
			const char* Doc;
		};

		const std::vector<FParamRow>& ParamRows()
		{
			static const std::vector<FParamRow> Rows = {
				{ "CrewTimeScale", &FCannonParams::CrewTimeScale, nullptr, "every crew time times this (0.5: twice as quick)" },
				{ "CrewSpread", &FCannonParams::CrewSpread, nullptr, "each crew's own pace, +- this share" },
				{ "CastLooseS", &FCannonParams::CastLooseS, nullptr, "s: lashings off, the gun eased in to load" },
				{ "LidS", &FCannonParams::LidS, nullptr, "s: a port lid hauled up or let down" },
				{ "SpongeS", &FCannonParams::SpongeS, nullptr, "s: wormed and sponged after a shot" },
				{ "LoadS", &FCannonParams::LoadS, nullptr, "s: cartridge, wad, shot, wad, rammed, pricked, primed" },
				{ "RunOutLongS", &FCannonParams::RunOutLongS, nullptr, "s: a long 24 hauled out on its side tackles, level" },
				{ "RunOutCarronadeS", &FCannonParams::RunOutCarronadeS, nullptr, "s: a carronade's bed run out on its slide" },
				{ "RunOutUphill", &FCannonParams::RunOutUphill, nullptr, "run out uphill takes 1 + this x sin(slope) longer" },
				{ "SecureS", &FCannonParams::SecureS, nullptr, "s: hauled against the sill and lashed for sea" },
				{ "PointS", &FCannonParams::PointS, nullptr, "s: pointing before a shot at will" },
				{ "LockDelayS", &FCannonParams::LockDelayS, nullptr, "s: lanyard to the charge (flint, pan, vent)" },
				{ "LockSpreadS", &FCannonParams::LockSpreadS, nullptr, "s: the lock's own scatter" },
				{ "BroadsideSpreadS", &FCannonParams::BroadsideSpreadS, nullptr, "s: a broadside's lanyards within this" },
				{ "RippleIntervalS", &FCannonParams::RippleIntervalS, nullptr, "s: ripple, gun after gun from forward" },
				{ "MisfireChance", &FCannonParams::MisfireChance, nullptr, "a flash in the pan (0..1)" },
				{ "ReprimeS", &FCannonParams::ReprimeS, nullptr, "s: primed again after a misfire" },
				{ "GasFactor", &FCannonParams::GasFactor, nullptr, "powder gas momentum = charge x this x muzzle velocity" },
				{ "RecoilScale", &FCannonParams::RecoilScale, nullptr, "every recoil impulse times this" },
				{ "RollMu", &FCannonParams::RollMu, nullptr, "a truck carriage rolling on the deck" },
				{ "SlideMu", &FCannonParams::SlideMu, nullptr, "a carronade's bed sliding on its slide" },
				{ "BreechingStretchM", &FCannonParams::BreechingStretchM, nullptr, "m: the breeching's give under a full recoil" },
				{ "BreechingDamping", &FCannonParams::BreechingDamping, nullptr, "the breeching's damping ratio" },
				{ "SmokePerChargeKg", &FCannonParams::SmokePerChargeKg, nullptr, "kg of smoke per kg of powder (black powder 0.55)" },
				{ "SmokeExtinction", &FCannonParams::SmokeExtinction, nullptr, "m^2/kg: how much a kg of smoke hides" },
				{ "SmokeOpacityCap", &FCannonParams::SmokeOpacityCap, nullptr, "the most one puff hides" },
				{ "PuffsLong", nullptr, &FCannonParams::PuffsLong, "puffs from a long gun's muzzle" },
				{ "PuffsCarronade", nullptr, &FCannonParams::PuffsCarronade, "puffs from a carronade's muzzle" },
				{ "PuffsVent", nullptr, &FCannonParams::PuffsVent, "puffs from the vent and pan" },
				{ "JetSpeedMs", &FCannonParams::JetSpeedMs, nullptr, "m/s: the blast's leading puff (long 24's charge)" },
				{ "JetSpreadDeg", &FCannonParams::JetSpreadDeg, nullptr, "deg: the jet's cone" },
				{ "JetDecayS", &FCannonParams::JetDecayS, nullptr, "s: the jet slows to the wind in about this" },
				{ "RingShare", &FCannonParams::RingShare, nullptr, "share of the puffs thrown round the muzzle" },
				{ "SigmaStartM", &FCannonParams::SigmaStartM, nullptr, "m: a puff's sigma at the muzzle" },
				{ "Diffusivity", &FCannonParams::Diffusivity, nullptr, "m^2/s: eddy diffusivity at sigma 1 m" },
				{ "DiffusivityPower", &FCannonParams::DiffusivityPower, nullptr, "K grows as sigma^this" },
				{ "BuoyancyMs2", &FCannonParams::BuoyancyMs2, nullptr, "m/s^2: the hot smoke's lift at first" },
				{ "BuoyancyDecayS", &FCannonParams::BuoyancyDecayS, nullptr, "s: the lift falls off (cooling)" },
				{ "WindTakeS", &FCannonParams::WindTakeS, nullptr, "s: a slow puff takes the wind's speed" },
				{ "SmokeMaxAgeS", &FCannonParams::SmokeMaxAgeS, nullptr, "s: the oldest smoke kept" },
				{ "MinPuffOpacity", &FCannonParams::MinPuffOpacity, nullptr, "a puff fainter than this is dropped" },
				{ "WaterLift", &FCannonParams::WaterLift, nullptr, "a puff's centre stays this many sigmas over the water" },
				{ "FlashS", &FCannonParams::FlashS, nullptr, "s: the muzzle flame's life" },
				{ "FlashLengthPerCbrtKg", &FCannonParams::FlashLengthPerCbrtKg, nullptr, "m of flame per cube root of the charge (kg)" },
				{ "FlashGlowM", &FCannonParams::FlashGlowM, nullptr, "m: smoke within this is lit by the flash" },
				{ "FlashLightCd", &FCannonParams::FlashLightCd, nullptr, "cd: the flash's light at its peak" },
				{ "FlashLightRadiusM", &FCannonParams::FlashLightRadiusM, nullptr, "m: the light's reach" },
				{ "PanFlashS", &FCannonParams::PanFlashS, nullptr, "s: the pan's flash" },
				{ "Sparks", nullptr, &FCannonParams::Sparks, "burning grains per shot" },
				{ "SparkSpeedMs", &FCannonParams::SparkSpeedMs, nullptr, "m/s: the sparks' speed" },
				{ "SparkLifeS", &FCannonParams::SparkLifeS, nullptr, "s: the sparks' life" },
				{ "FlameNits", &FCannonParams::FlameNits, nullptr, "cd/m^2: the flame's core at its peak" },
				{ "SparkNits", &FCannonParams::SparkNits, nullptr, "cd/m^2: a burning grain" },
				{ "SmokeGlowNits", &FCannonParams::SmokeGlowNits, nullptr, "cd/m^2: smoke at the flash, lit from inside" },
				{ "SmokeAlbedo", &FCannonParams::SmokeAlbedo, nullptr, "the smoke's colour (0..1 grey)" },
				{ "SmokeForwardScatter", &FCannonParams::SmokeForwardScatter, nullptr, "Henyey-Greenstein g of the smoke toward the sun" },
				{ "SmokeEdgeSoftness", &FCannonParams::SmokeEdgeSoftness, nullptr, "0 billowed edges .. 1 a soft Gaussian" },
				{ "SmokeCoreGain", &FCannonParams::SmokeCoreGain, nullptr, "a puff's core this much denser than its Gaussian" },
				{ "SmokeDepthFadeM", &FCannonParams::SmokeDepthFadeM, nullptr, "m: the smoke fades into surfaces over this" },
			};
			return Rows;
		}

		const FParamRow* FindRow(const std::string& Key)
		{
			const std::string K = Lower(Trim(Key));
			for (const FParamRow& R : ParamRows())
			{
				if (Lower(R.Name) == K) return &R;
			}
			return nullptr;
		}
	}

	const char* GunStateName(EGunState S)
	{
		switch (S)
		{
		case EGunState::Housed: return "Housed";
		case EGunState::CastingLoose: return "CastingLoose";
		case EGunState::Waiting: return "Waiting";
		case EGunState::Sponging: return "Sponging";
		case EGunState::Loading: return "Loading";
		case EGunState::Loaded: return "Loaded";
		case EGunState::OpeningLid: return "OpeningLid";
		case EGunState::RunningOut: return "RunningOut";
		case EGunState::Ready: return "Ready";
		case EGunState::Lock: return "Lock";
		case EGunState::Recoil: return "Recoil";
		case EGunState::Spent: return "Spent";
		case EGunState::RunningIn: return "RunningIn";
		case EGunState::ClosingLid: return "ClosingLid";
		case EGunState::Securing: return "Securing";
		default: return "?";
		}
	}

	// ---------------------------------------------------------------------------------------------------------------------
	// The guns.

	std::vector<FCannonMount> FrigateCannonMounts()
	{
		std::vector<FCannonMount> Out;
		auto Row = [&Out](ECannonKind Kind, ECannonSide Side, int32_t Port, const char* Id, const Vec3& Origin, const Vec3& AX,
			const Vec3& AY, const Vec3& AZ, double Housed, double RunIn, double RunOut, double Slide, double Elev, double Lid,
			double Lo, double Hi)
		{
			FCannonMount M;
			M.Kind = Kind;
			M.Side = Side;
			M.Port = Port;
			std::snprintf(M.Id, sizeof(M.Id), "%s", Id);
			M.Origin = Origin;
			M.AxisX = AX;
			M.AxisY = AY;
			M.AxisZ = AZ;
			M.HousedX = Housed;
			M.RunInX = RunIn;
			M.RunOutX = RunOut;
			M.SlideX = Slide;
			M.HousedElevationDeg = Elev;
			M.LidOpenDeg = Lid;
			M.MinElevationDeg = Lo;
			M.MaxElevationDeg = Hi;
			Out.push_back(M);
		};
		// The last row's lid hinge, when the model gives it.
		auto Hinge = [&Out](const Vec3& Origin, const Vec3& AX, const Vec3& AY, const Vec3& AZ)
		{
			if (Out.empty()) return;
			FCannonMount& M = Out.back();
			M.bHinge = true;
			M.HingeOrigin = Origin;
			M.HingeX = AX;
			M.HingeY = AY;
			M.HingeZ = AZ;
		};
#include "FrigateGunData.inl"
		(void)Hinge;   // (no Hinge rows until the model's guns.json gives the lids' frames)
		return Out;
	}

	FCannonKindSpec FCannonKindSpec::Make(ECannonKind Kind)
	{
		FCannonKindSpec K;
		if (Kind == ECannonKind::Long24)
		{
			// The long 24-pounder (Tools/shipkit/frigate/guns_1797.json long24): 9 ft 6 in, about 50 cwt (US Navy caption:
			// Constitution's 24s are 5,600 lb with their... the barrel alone is the 50 cwt, 2,540 kg). Its truck carriage of
			// oak with iron work about 11 cwt (Muller's tables put a 24's carriage near a fifth of the gun): 560 kg.
			K.GunKg = 2540.0;
			K.CarriageKg = 560.0;
			K.ShotKg = 10.9;              // 24 lb (English pounds): the shot itself
			K.ChargeKg = 3.63;            // 8 lb, a third of the shot's weight: the service charge
			K.MuzzleVelocityMs = 490.0;   // ~1,600 ft/s with a third charge (Hutton's ballistic pendulum, 1780s)
			K.BoreM = 5.823 * kInch;
			K.CarriageZ = 0.0;
			K.BarrelPivot = Vec3(0.0, 0.0, 0.9525);            // guns.json long24.barrel_in_carriage_m
			// The muzzle's face 114 in from the base ring's back, the trunnions 48.86 in from it: 65.14 in ahead of them, on
			// the bore 0.6 in over the trunnions' axis (guns.json bore_over_trunnions_m).
			K.Muzzle = Vec3((114.0 - 48.86) * kInch, 0.0, 0.01524);
			K.Vent = Vec3(-1.1496, 0.0, 0.25034);              // guns.json vent_in_barrel_m
			K.Pan = Vec3(-1.1496, 0.02032, 0.25796);
			K.TruckRadiusFore = 0.2413;
			K.TruckRadiusHind = 0.2159;
		}
		else
		{
			// The 32-pounder carronade (guns_1797.json carronade32): 17 cwt, its bed about 4 cwt; a twelfth charge drives
			// its shot at about 300 m/s (carronades were short and loose-fitting: about 60% of a long gun's velocity).
			K.GunKg = 864.0;
			K.CarriageKg = 200.0;
			K.ShotKg = 14.5;
			K.ChargeKg = 1.21;
			K.MuzzleVelocityMs = 300.0;
			K.BoreM = 6.25 * kInch;
			K.CarriageZ = 0.43688;                              // guns.json carronade32.bed_z_m
			K.BarrelPivot = Vec3(0.0, 0.0, 0.23622);           // barrel_in_bed_m: the loop's bolt
			// The muzzle 42 in from the base ring's back, the loop's bolt 3.7 in behind it: 45.7 in ahead of the bolt, on
			// the bore 0.24384 m over it (bore_over_bolt_m).
			K.Muzzle = Vec3((42.0 + 3.7) * kInch, 0.0, 0.24384);
			K.Vent = Vec3(-0.36576, 0.0, 0.44339);
			K.Pan = Vec3(-0.36576, 0.02032, 0.45101);
		}
		return K;
	}

	Vec3 FGun::CarriageToShip(const Vec3& P, double CarriageZ) const
	{
		const double Lx = X + P.X, Ly = P.Y, Lz = CarriageZ + P.Z;
		return Mount.Origin + Mount.AxisX * Lx + Mount.AxisY * Ly + Mount.AxisZ * Lz;
	}

	Vec3 FGun::BarrelToShip(const Vec3& P, const FCannonKindSpec& K) const
	{
		// Elevation raises the muzzle: +X turns toward +Z.
		const double E = ElevationDeg * kDegToRad;
		const double C = std::cos(E), S = std::sin(E);
		const Vec3 R(P.X * C - P.Z * S, P.Y, P.X * S + P.Z * C);
		return CarriageToShip(K.BarrelPivot + R, K.CarriageZ);
	}

	Vec3 FGun::BoreDir() const
	{
		const double E = ElevationDeg * kDegToRad;
		return (Mount.AxisX * std::cos(E) + Mount.AxisZ * std::sin(E)).Normalized();
	}

	// ---------------------------------------------------------------------------------------------------------------------
	// The parameters.

	bool FCannonParams::Set(const std::string& Key, double Value)
	{
		const FParamRow* R = FindRow(Key);
		if (!R || !std::isfinite(Value)) return false;
		if (R->D) this->*(R->D) = Value;
		else this->*(R->I) = int32_t(std::lround(Value));
		return true;
	}

	bool FCannonParams::Get(const std::string& Key, double& Value) const
	{
		const FParamRow* R = FindRow(Key);
		if (!R) return false;
		Value = R->D ? this->*(R->D) : double(this->*(R->I));
		return true;
	}

	int32_t FCannonParams::ApplyOverrides(const std::string& Text, std::string* Unknown)
	{
		int32_t Applied = 0;
		std::string Item;
		auto Take = [&](const std::string& Raw)
		{
			std::string S = Raw;
			const size_t Hash = S.find('#');
			if (Hash != std::string::npos) S = S.substr(0, Hash);
			S = Trim(S);
			if (S.empty()) return;
			const size_t Eq = S.find('=');
			if (Eq == std::string::npos) { if (Unknown) *Unknown += (Unknown->empty() ? "" : ",") + S; return; }
			const std::string Key = Trim(S.substr(0, Eq));
			const std::string Val = Trim(S.substr(Eq + 1));
			char* End = nullptr;
			const double V = std::strtod(Val.c_str(), &End);
			if (End == Val.c_str() || !Set(Key, V)) { if (Unknown) *Unknown += (Unknown->empty() ? "" : ",") + Key; return; }
			++Applied;
		};
		for (char C : Text)
		{
			if (C == ',' || C == '\n' || C == ';' || C == '\r') { Take(Item); Item.clear(); }
			else Item += C;
		}
		Take(Item);
		return Applied;
	}

	std::string FCannonParams::Dump() const
	{
		std::string Out = "# Cannon fire tuning (docs/cannon-fire/tuning.md). Key = value, one per line; '#' starts a comment.\n";
		char Line[256];
		for (const FParamRow& R : ParamRows())
		{
			if (R.D) std::snprintf(Line, sizeof(Line), "%-22s = %-10.6g # %s\n", R.Name, this->*(R.D), R.Doc);
			else std::snprintf(Line, sizeof(Line), "%-22s = %-10d # %s\n", R.Name, int(this->*(R.I)), R.Doc);
			Out += Line;
		}
		return Out;
	}

	std::vector<std::string> FCannonParams::Names()
	{
		std::vector<std::string> Out;
		for (const FParamRow& R : ParamRows()) Out.push_back(R.Name);
		return Out;
	}

	// ---------------------------------------------------------------------------------------------------------------------
	// The battery.

	void FCannonBattery::Init(const std::vector<FCannonMount>& Mounts, uint64_t Seed)
	{
		Rng.Reseed(Seed);
		GunList.clear();
		GunList.reserve(Mounts.size());
		for (size_t I = 0; I < Mounts.size(); ++I)
		{
			FGun G;
			G.Mount = Mounts[I];
			G.Seed = HashCombine(Seed, uint64_t(I) + 1);
			FPortableRandom Own(G.Seed);
			G.Pace = 1.0 + Params.CrewSpread * (2.0 * Own.Uniform01() - 1.0);
			if (G.Mount.Kind == ECannonKind::Long24)
			{
				G.X = G.Mount.HousedX;
				G.ElevationDeg = G.Mount.HousedElevationDeg;
			}
			else
			{
				// A carronade at sea is run out on its slide and lashed (the spar deck's ports are open).
				G.X = G.Mount.RunOutX;
				G.ElevationDeg = 0.0;
			}
			G.State = EGunState::Housed;
			GunList.push_back(G);
		}
		Target[0] = Target[1] = ETarget::Housed;
		bVolleyPending[0] = bVolleyPending[1] = false;
		UpdateBreeching();
	}

	void FCannonBattery::UpdateBreeching()
	{
		for (int32_t K = 0; K < 2; ++K)
		{
			const ECannonKind Kind = K == 0 ? ECannonKind::Long24 : ECannonKind::Carronade32;
			const FCannonKindSpec& S = Spec(Kind);
			// The recoil's speed when the breeching comes taut, on a level deck: the shot's speed less what friction took
			// over the run in (the typical gun's run out to run in). A gun that arrives faster stretches it further.
			double Run = K == 0 ? 1.63 : 0.76;
			for (const FGun& G : GunList)
			{
				if (G.Mount.Kind == Kind) { Run = std::max(0.1, G.Mount.RunOutX - G.Mount.RunInX); break; }
			}
			const double M = S.RecoilingKg();
			const double V0 = RecoilImpulse(Kind) / M;
			const double Mu = K == 0 ? Params.RollMu : Params.SlideMu;
			const double Vt2 = std::max(V0 * V0 - 2.0 * Mu * kG * Run, 0.25);
			const double Stretch = std::max(Params.BreechingStretchM, 0.01);
			BreechK[K] = M * Vt2 / (Stretch * Stretch);
			BreechC[K] = 2.0 * Params.BreechingDamping * std::sqrt(BreechK[K] * M);
		}
	}

	double FCannonBattery::RecoilImpulse(ECannonKind Kind) const
	{
		const FCannonKindSpec& S = Spec(Kind);
		return Params.RecoilScale * S.MuzzleVelocityMs * (S.ShotKg + Params.GasFactor * S.ChargeKg);
	}

	void FCannonBattery::Enter(FGun& G, EGunState S, double Duration)
	{
		G.State = S;
		G.StateT = 0.0;
		G.StateDuration = Duration;
		G.MoveFrom = G.X;
	}

	void FCannonBattery::Order(ECannonOrder Order, ECannonSide Side, double Now)
	{
		for (int32_t S = 0; S < 2; ++S)
		{
			if (Side != ECannonSide::Both && SideIndex(Side) != S) continue;
			switch (Order)
			{
			case ECannonOrder::CastLoose: if (Target[S] == ETarget::Housed) Target[S] = ETarget::Loose; break;
			case ECannonOrder::Load: Target[S] = std::max(Target[S], ETarget::Loaded); if (Target[S] == ETarget::Firing) Target[S] = ETarget::Out; break;
			case ECannonOrder::RunOut: Target[S] = Target[S] == ETarget::Firing ? ETarget::Firing : ETarget::Out; break;
			case ECannonOrder::Fire:
				if (FireMode == ECannonFireMode::AtWill) Target[S] = ETarget::Firing;
				else
				{
					// A broadside (or ripple) on the word: the guns ready now, or the side as soon as it is ready.
					Target[S] = ETarget::Out;
					bVolleyPending[S] = true;
					ScheduleVolley(S, Now);
				}
				break;
			case ECannonOrder::CeaseFire:
				bVolleyPending[S] = false;
				if (Target[S] == ETarget::Firing) Target[S] = ETarget::Out;
				for (FGun& G : GunList)
				{
					if (SideIndex(G.Mount.Side) == S && G.State == EGunState::Ready) G.FireAt = -1.0;   // the lanyards not yet pulled
				}
				break;
			case ECannonOrder::Secure:
				bVolleyPending[S] = false;
				Target[S] = ETarget::Housed;
				for (FGun& G : GunList)
				{
					if (SideIndex(G.Mount.Side) == S) G.FireAt = -1.0;
				}
				break;
			}
		}
	}

	void FCannonBattery::MakeReady(ECannonSide Side)
	{
		for (FGun& G : GunList)
		{
			if (!OnSide(G, Side)) continue;
			G.X = G.Mount.RunOutX;
			G.V = 0.0;
			G.ElevationDeg = 0.0;
			G.LidDeg = G.Mount.LidOpenDeg;
			G.bLoaded = true;
			G.FireAt = -1.0;
			Enter(G, EGunState::Ready, 0.0);
		}
		for (int32_t S = 0; S < 2; ++S)
		{
			if (Side == ECannonSide::Both || SideIndex(Side) == S) Target[S] = std::max(Target[S], ETarget::Out);
		}
	}

	double FCannonBattery::ToReady(const FGun& G) const
	{
		const bool bLong = G.Mount.Kind == ECannonKind::Long24;
		const double Lid = bLong && G.LidDeg < G.Mount.LidOpenDeg - 1e-3 ? CrewTime(G, Params.LidS) : 0.0;
		const double Out = CrewTime(G, bLong ? Params.RunOutLongS : Params.RunOutCarronadeS);
		const double Load = CrewTime(G, Params.LoadS);
		const double Left = std::max(G.StateDuration - G.StateT, 0.0);
		switch (G.State)
		{
		case EGunState::Ready: return 0.0;
		case EGunState::RunningOut: return Left;
		case EGunState::OpeningLid: return Left + Out;
		case EGunState::Loaded: return Lid + Out;
		case EGunState::Loading: return Left + Lid + Out;
		case EGunState::Sponging: return Left + Load + Lid + Out;
		case EGunState::Recoil: return CrewTime(G, Params.SpongeS) + Load + Lid + Out;
		case EGunState::Spent: return CrewTime(G, Params.SpongeS) + Load + Lid + Out;
		case EGunState::Waiting: return (G.bLoaded ? 0.0 : Load) + Lid + Out;
		case EGunState::CastingLoose: return Left + Load + Lid + Out;
		case EGunState::Housed: return CrewTime(G, Params.CastLooseS) + Load + Lid + Out;
		default: return -1.0;
		}
	}

	void FCannonBattery::ScheduleVolley(int32_t S, double Now)
	{
		if (!bVolleyPending[S]) return;
		// The volley waits for every gun that is coming to Ready (loading, running out) on the side; a gun housed or left
		// idle doesn't hold it. A gun already firing (its lock, its recoil) doesn't either.
		bool bWaiting = false;
		int32_t ReadyCount = 0;
		for (const FGun& G : GunList)
		{
			if (SideIndex(G.Mount.Side) != S) continue;
			if (G.State == EGunState::Ready) { if (G.FireAt < 0.0) ++ReadyCount; continue; }
			const EGunState St = G.State;
			const bool bComing = St == EGunState::RunningOut || St == EGunState::OpeningLid || St == EGunState::Loading
				|| St == EGunState::Sponging || St == EGunState::CastingLoose || St == EGunState::Loaded
				|| (St == EGunState::Waiting && Target[S] >= ETarget::Loaded) || St == EGunState::Spent || St == EGunState::Housed;
			if (bComing) bWaiting = true;
		}
		if (bWaiting || ReadyCount == 0) return;
		// Fire: a broadside's lanyards each within the spread; a ripple gun after gun from forward.
		std::vector<int32_t> Order;
		for (int32_t I = 0; I < Num(); ++I)
		{
			const FGun& G = GunList[size_t(I)];
			if (SideIndex(G.Mount.Side) == S && G.State == EGunState::Ready && G.FireAt < 0.0) Order.push_back(I);
		}
		std::stable_sort(Order.begin(), Order.end(), [&](int32_t A, int32_t B)
			{ return GunList[size_t(A)].Mount.Origin.X > GunList[size_t(B)].Mount.Origin.X; });
		for (size_t K = 0; K < Order.size(); ++K)
		{
			FGun& G = GunList[size_t(Order[K])];
			G.FireAt = FireMode == ECannonFireMode::Ripple ? Now + double(K) * Params.RippleIntervalS
				: Now + Rng.Uniform(0.0, std::max(Params.BroadsideSpreadS, 0.0));
		}
		bVolleyPending[S] = false;
	}

	void FCannonBattery::Fire(int32_t Index, FGun& G, double Now)
	{
		const FCannonKindSpec& K = Spec(G.Mount.Kind);
		FCannonShot Shot;
		Shot.Gun = Index;
		Shot.Time = Now;
		Shot.MuzzleShip = G.BarrelToShip(K.Muzzle, K);
		Shot.BoreShip = G.BoreDir();
		Shot.ChargeKg = K.ChargeKg;
		FPortableRandom Own(HashCombine(G.Seed, uint64_t(G.Shots) * 7919u + 11u));
		Shot.bMisfire = Own.Uniform01() < Params.MisfireChance;
		if (Shot.bMisfire)
		{
			Shot.ImpulseNs = 0.0;
			StepShots.push_back(Shot);
			G.bMisfired = true;
			// Primed again; it fires again when the order stands (at will, or a volley still going).
			Enter(G, EGunState::Ready, 0.0);
			G.FireAt = TargetFor(G) == ETarget::Firing || FireMode != ECannonFireMode::AtWill ? Now + CrewTime(G, Params.ReprimeS) : -1.0;
			return;
		}
		Shot.ImpulseNs = RecoilImpulse(G.Mount.Kind);
		StepShots.push_back(Shot);
		G.bLoaded = false;
		G.bMisfired = false;
		++G.Shots;
		Enter(G, EGunState::Recoil, 0.0);
		// The charge's push on the gun: the gun and its carriage fly in along the port's X (the bore's slope puts a little
		// of it into the deck, which takes it).
		const Vec3 Bore = G.BoreDir();
		const double AlongX = Bore.Dot(G.Mount.AxisX);
		G.V = -Shot.ImpulseNs * AlongX / K.RecoilingKg();
		G.RestT = 0.0;
	}

	void FCannonBattery::Step(const FCannonStepInput& In)
	{
		StepShots.clear();
		StepLocks.clear();
		StepForce = Vec3();
		StepMoment = Vec3();
		if (In.Dt <= 0.0) return;
		for (int32_t S = 0; S < 2; ++S)
		{
			if (bVolleyPending[S]) ScheduleVolley(S, In.Time);
		}
		for (int32_t I = 0; I < Num(); ++I) StepGun(I, GunList[size_t(I)], In);
		StepForce = StepForce / In.Dt;
		StepMoment = StepMoment / In.Dt;
	}

	void FCannonBattery::StepGun(int32_t Index, FGun& G, const FCannonStepInput& In)
	{
		const bool bLong = G.Mount.Kind == ECannonKind::Long24;
		const FCannonKindSpec& K = Spec(G.Mount.Kind);
		const double Dt = In.Dt;
		const double Now = In.Time;
		const ETarget T = TargetFor(G);
		const double Gx = In.GravityShip.Dot(G.Mount.AxisX);          // gravity along the port's X (+: rolls her out)
		const double Gn = std::max(-In.GravityShip.Dot(G.Mount.AxisZ), 0.0);   // pressing her to the deck
		const double LidOpen = G.Mount.LidOpenDeg;
		const bool bLidShut = bLong && LidOpen > 0.0 && G.LidDeg < LidOpen - 1e-3;
		const double RunOutBase = bLong ? Params.RunOutLongS : Params.RunOutCarronadeS;
		// Uphill (the weather side heeled): gravity pulls her inboard.
		const double Uphill = std::max(-Gx / kG, 0.0);
		const double RunOutS = CrewTime(G, RunOutBase) * (1.0 + Params.RunOutUphill * Uphill);

		G.StateT += Dt;
		auto Done = [&]() { return G.StateT >= G.StateDuration; };
		auto MoveTo = [&](double To)
		{
			const double Was = G.X;
			const double A = G.StateDuration > 0.0 ? SmoothStep01(G.StateT / G.StateDuration) : 1.0;
			G.X = G.MoveFrom + (To - G.MoveFrom) * A;
			G.V = Dt > 0.0 ? (G.X - Was) / Dt : 0.0;
		};
		auto TurnTrucks = [&](double DX)
		{
			if (K.TruckRadiusFore > 0.0) G.TruckTurn += DX / K.TruckRadiusFore;
		};
		const double XWas = G.X;

		switch (G.State)
		{
		case EGunState::Housed:
			G.V = 0.0;
			if (T >= ETarget::Loose) Enter(G, EGunState::CastingLoose, CrewTime(G, Params.CastLooseS));
			break;
		case EGunState::CastingLoose:
		{
			// The lashings cast off, the quoin in, the gun eased in to its loading place; the breech lifted level.
			const double A = SmoothStep01(G.StateT / std::max(G.StateDuration, 1e-6));
			const double From = bLong ? G.Mount.HousedX : G.Mount.RunOutX;
			G.X = From + (G.Mount.RunInX - From) * SmoothStep01((A - 0.3) / 0.7);
			G.ElevationDeg = (bLong ? G.Mount.HousedElevationDeg : 0.0) * (1.0 - SmoothStep01(A / 0.4));
			if (Done()) { G.X = G.Mount.RunInX; G.ElevationDeg = 0.0; Enter(G, EGunState::Waiting, 0.0); }
			break;
		}
		case EGunState::Waiting:
		case EGunState::Loaded:
			G.V = 0.0;
			if (T == ETarget::Housed)
			{
				if (bLong && G.LidDeg > 1e-3) Enter(G, EGunState::ClosingLid, CrewTime(G, Params.LidS));
				else Enter(G, EGunState::Securing, CrewTime(G, Params.SecureS));
			}
			else if (!G.bLoaded && T >= ETarget::Loaded) Enter(G, EGunState::Loading, CrewTime(G, Params.LoadS));
			else if (G.bLoaded && G.State == EGunState::Waiting) Enter(G, EGunState::Loaded, 0.0);
			else if (G.bLoaded && T >= ETarget::Out)
			{
				if (bLidShut) Enter(G, EGunState::OpeningLid, CrewTime(G, Params.LidS));
				else Enter(G, EGunState::RunningOut, RunOutS);
			}
			break;
		case EGunState::Sponging:
			G.V = 0.0;
			if (Done())
			{
				if (T >= ETarget::Loaded) Enter(G, EGunState::Loading, CrewTime(G, Params.LoadS));
				else Enter(G, EGunState::Waiting, 0.0);
			}
			break;
		case EGunState::Loading:
			G.V = 0.0;
			if (Done()) { G.bLoaded = true; Enter(G, EGunState::Loaded, 0.0); }
			break;
		case EGunState::OpeningLid:
			G.V = 0.0;
			G.LidDeg = LidOpen * SmoothStep01(G.StateT / std::max(G.StateDuration, 1e-6));
			if (Done()) { G.LidDeg = LidOpen; Enter(G, EGunState::RunningOut, RunOutS); }
			break;
		case EGunState::RunningOut:
			MoveTo(G.Mount.RunOutX);
			if (Done()) { G.X = G.Mount.RunOutX; G.V = 0.0; Enter(G, EGunState::Ready, 0.0); G.FireAt = -1.0; }
			break;
		case EGunState::Ready:
			G.V = 0.0;
			if (T == ETarget::Housed || T == ETarget::Loaded)
			{
				// Run in: to secure, or held loaded inboard.
				Enter(G, EGunState::RunningIn, CrewTime(G, RunOutBase));
				break;
			}
			if (T == ETarget::Firing && G.FireAt < 0.0) G.FireAt = Now + CrewTime(G, Params.PointS) * (0.5 + Rng.Uniform01());
			if (G.FireAt >= 0.0 && Now >= G.FireAt)
			{
				G.FireAt = -1.0;
				FPortableRandom Own(HashCombine(G.Seed, uint64_t(G.Shots) * 104729u + 3u));
				Enter(G, EGunState::Lock, std::max(Params.LockDelayS + Params.LockSpreadS * (2.0 * Own.Uniform01() - 1.0), 0.0));
				StepLocks.push_back(Index);
			}
			break;
		case EGunState::Lock:
			G.V = 0.0;
			if (Done()) Fire(Index, G, Now);
			break;
		case EGunState::Recoil:
		{
			// Sub-stepped: the breeching is stiff (it brings three tonnes up in a few inches).
			const int32_t KindIndex = bLong ? 0 : 1;
			const double M = K.RecoilingKg();
			const double Mu = bLong ? Params.RollMu : Params.SlideMu;
			const int32_t Steps = std::max(1, int32_t(std::ceil(Dt / (1.0 / 1200.0))));
			const double H = Dt / double(Steps);
			const Vec3 At = G.CarriageToShip(Vec3(0.0, 0.0, 0.3), K.CarriageZ);   // about where the deck and breeching take her
			for (int32_t Sub = 0; Sub < Steps; ++Sub)
			{
				double FShip = 0.0;   // the ship's force on the gun along X (friction, breeching)
				const double Stretch = G.Mount.RunInX - G.X;
				if (Stretch > 0.0) FShip += std::max(BreechK[KindIndex] * Stretch - BreechC[KindIndex] * G.V, 0.0);
				const double Drive = M * Gx + FShip;
				const double Fric = Mu * M * Gn;
				double Fnet;
				if (std::fabs(G.V) > 1e-4)
				{
					const double Ff = -Sign(G.V) * Fric;
					FShip += Ff;
					Fnet = Drive + Ff;
					const double VNew = G.V + Fnet / M * H;
					// Friction stops her; it never turns her round.
					if (VNew * G.V < 0.0 && std::fabs(Drive) <= Fric) { FShip = -M * G.V / H - M * Gx; G.V = 0.0; }
					else G.V = VNew;
				}
				else
				{
					// Still: friction holds her unless the slope and breeching beat it.
					if (std::fabs(Drive) <= Fric) { FShip += -Drive; Fnet = 0.0; G.V = 0.0; }
					else { const double Ff = -Sign(Drive) * Fric; FShip += Ff; Fnet = Drive + Ff; G.V += Fnet / M * H; }
				}
				// Once she stops flying in, the train tackle (hooked behind her) holds her: a gun on the lee side, or sprung
				// back off the breeching, doesn't roll out again.
				if (G.V > 0.0) { FShip += -M * G.V / H; G.V = 0.0; }
				G.X += G.V * H;
				// The side stops her rolling out past the run-out place.
				if (G.X > G.Mount.RunOutX) { G.X = G.Mount.RunOutX; G.V = std::min(G.V, 0.0); }
				// The ship takes the reaction (N s over the sub-step).
				const Vec3 F = G.Mount.AxisX * (-FShip);
				StepForce += F * H;
				StepMoment += At.Cross(F) * H;
			}
			G.RestT = std::fabs(G.V) < 0.03 ? G.RestT + Dt : 0.0;
			if (G.RestT > 0.25 || G.StateT > 6.0)
			{
				G.V = 0.0;
				Enter(G, EGunState::Spent, 0.0);
			}
			break;
		}
		case EGunState::Spent:
			G.V = 0.0;
			// The crew hold her with the train tackle; sponge when the side is to fire again or load.
			if (T >= ETarget::Loaded) Enter(G, EGunState::Sponging, CrewTime(G, Params.SpongeS));
			else if (T == ETarget::Housed) Enter(G, EGunState::Sponging, CrewTime(G, Params.SpongeS));
			else if (T == ETarget::Loose) Enter(G, EGunState::Sponging, CrewTime(G, Params.SpongeS));
			break;
		case EGunState::RunningIn:
			MoveTo(G.Mount.RunInX);
			if (Done()) { G.X = G.Mount.RunInX; G.V = 0.0; Enter(G, G.bLoaded ? EGunState::Loaded : EGunState::Waiting, 0.0); }
			break;
		case EGunState::ClosingLid:
			G.V = 0.0;
			G.LidDeg = LidOpen * (1.0 - SmoothStep01(G.StateT / std::max(G.StateDuration, 1e-6)));
			if (Done()) { G.LidDeg = 0.0; Enter(G, EGunState::Securing, CrewTime(G, Params.SecureS)); }
			break;
		case EGunState::Securing:
		{
			const double A = SmoothStep01(G.StateT / std::max(G.StateDuration, 1e-6));
			const double To = bLong ? G.Mount.HousedX : G.Mount.RunOutX;
			G.X = G.MoveFrom + (To - G.MoveFrom) * SmoothStep01(A / 0.7);
			G.ElevationDeg = bLong ? G.Mount.HousedElevationDeg * SmoothStep01((A - 0.6) / 0.4) : 0.0;
			if (Done()) { G.X = To; G.V = 0.0; G.ElevationDeg = bLong ? G.Mount.HousedElevationDeg : 0.0; Enter(G, EGunState::Housed, 0.0); }
			break;
		}
		default:
			break;
		}
		TurnTrucks(G.X - XWas);
	}

	FCannonSideStatus FCannonBattery::Status(ECannonSide Side) const
	{
		FCannonSideStatus S;
		for (const FGun& G : GunList)
		{
			if (!OnSide(G, Side)) continue;
			++S.Guns;
			++S.ByState[int32_t(G.State)];
			if (G.State == EGunState::Ready) ++S.Ready;
			if (G.bLoaded) ++S.Loaded;
			S.Shots += G.Shots;
			const ETarget T = TargetFor(G);
			if (G.State != EGunState::Ready && T >= ETarget::Out)
			{
				const double R = ToReady(G);
				if (R >= 0.0 && (S.NextReadyS < 0.0 || R < S.NextReadyS)) S.NextReadyS = R;
			}
		}
		return S;
	}

	// ---------------------------------------------------------------------------------------------------------------------
	// The smoke and flame.

	double FSmokePuff::Opacity(const FCannonParams& Pr) const
	{
		const double S2 = std::max(Sigma * Sigma, 1e-4);
		const double Tau = Pr.SmokeExtinction * MassKg / (kTwoPi * S2);
		return std::min(1.0 - std::exp(-Tau), Pr.SmokeOpacityCap);
	}

	double FCannonFlash::Intensity(double T) const
	{
		if (Life <= 0.0) return 0.0;
		const double U = (T - Start) / Life;
		if (U < 0.0 || U > 1.0) return 0.0;
		// The primary flash at once, then the secondary flame burning in the air dying away.
		if (U < 0.06) return U / 0.06;
		return std::pow((1.0 - U) / 0.94, 1.6);
	}

	void FCannonSmoke::Clear()
	{
		PuffList.clear();
		FlashList.clear();
		SparkList.clear();
		MergeCount = 0;
	}

	double FCannonSmoke::TotalMass() const
	{
		double M = 0.0;
		for (const FSmokePuff& P : PuffList) M += P.MassKg;
		return M;
	}

	void FCannonSmoke::EmitShot(const Vec3& Muzzle, const Vec3& BoreIn, const Vec3& Vent, const Vec3& ShipV, double ChargeKg,
		bool bMisfire, double Now, bool bLong)
	{
		const Vec3 Bore = BoreIn.Normalized();
		// Two axes across the bore for the cone and the ring.
		const Vec3 Ref = std::fabs(Bore.Z) < 0.9 ? Vec3(0, 0, 1) : Vec3(1, 0, 0);
		const Vec3 A1 = Bore.Cross(Ref).Normalized();
		const Vec3 A2 = Bore.Cross(A1).Normalized();
		const double Scale = std::cbrt(std::max(ChargeKg, 1e-3) / kLongChargeKg);

		// The pan's flash and its puff go off with every pull of the lanyard, fired or not.
		{
			FCannonFlash F;
			F.P = Vent;
			F.Dir = Vec3(0, 0, 1);
			F.Start = Now;
			F.Life = Params.PanFlashS;
			F.LengthM = 0.35;
			F.bPan = true;
			FlashList.push_back(F);
			const double VentMass = (bMisfire ? 0.02 : 0.03 * Params.SmokePerChargeKg * ChargeKg);
			const int32_t NV = std::max(1, Params.PuffsVent);
			for (int32_t I = 0; I < NV; ++I)
			{
				FSmokePuff P;
				P.P = Vent + Vec3(0, 0, 0.05);
				P.V = ShipV + Vec3(Rng.Uniform(-0.3, 0.3), Rng.Uniform(-0.3, 0.3), Rng.Uniform(1.5, 3.5));
				P.Sigma = 0.12;
				P.MassKg = VentMass / double(NV);
				P.Heat = 0.6;
				P.Seed = float(Rng.Uniform01());
				P.Source = 2;
				PuffList.push_back(P);
			}
		}
		if (bMisfire) return;

		const double Mass = Params.SmokePerChargeKg * ChargeKg;
		const int32_t N = std::max(2, bLong ? Params.PuffsLong : Params.PuffsCarronade);
		const int32_t NRing = std::clamp(int32_t(std::lround(double(N) * Params.RingShare)), 0, N - 1);
		const int32_t NJet = N - NRing;
		const double Jet = Params.JetSpeedMs * Scale;
		const double Cone = std::tan(Params.JetSpreadDeg * kDegToRad);
		// The jet: the leading puffs fast, the trailing ones slow (the blast's column, front to back).
		for (int32_t I = 0; I < NJet; ++I)
		{
			const double U = (double(I) + 0.5) / double(NJet);
			const double Ang = Rng.Uniform(0.0, kTwoPi);
			const double R = Cone * std::sqrt(Rng.Uniform01());
			const Vec3 Dir = (Bore + A1 * (R * std::cos(Ang)) + A2 * (R * std::sin(Ang))).Normalized();
			FSmokePuff P;
			P.P = Muzzle + Bore * (0.2 + 0.4 * Rng.Uniform01());
			P.V = ShipV + Dir * (Jet * (0.15 + 0.85 * U * U) * Rng.Uniform(0.85, 1.15));
			P.Sigma = Params.SigmaStartM * Scale * Rng.Uniform(0.6, 1.3);
			// The leading puffs carry less: most of the smoke is in the column's body near the muzzle.
			P.MassKg = Mass * (1.0 - Params.RingShare) / double(NJet);
			P.Seed = float(Rng.Uniform01());
			P.Source = 0;
			PuffList.push_back(P);
		}
		// The ring: thrown out round the muzzle as the blast's vortex ring, a little forward.
		for (int32_t I = 0; I < NRing; ++I)
		{
			const double Ang = kTwoPi * (double(I) + Rng.Uniform01()) / double(std::max(NRing, 1));
			const Vec3 Dir = (A1 * std::cos(Ang) + A2 * std::sin(Ang) + Bore * 0.35).Normalized();
			FSmokePuff P;
			P.P = Muzzle + Bore * 0.3;
			P.V = ShipV + Dir * (0.22 * Jet * Rng.Uniform(0.6, 1.0));
			P.Sigma = Params.SigmaStartM * Scale * Rng.Uniform(0.8, 1.4);
			P.MassKg = Mass * Params.RingShare / double(NRing);
			P.Seed = float(Rng.Uniform01());
			P.Source = 1;
			PuffList.push_back(P);
		}
		// The flame.
		FCannonFlash F;
		F.P = Muzzle;
		F.Dir = Bore;
		F.Start = Now;
		F.Life = Params.FlashS * std::max(Scale, 0.5);
		F.LengthM = Params.FlashLengthPerCbrtKg * std::cbrt(std::max(ChargeKg, 1e-3));
		FlashList.push_back(F);
		for (int32_t I = 0; I < Params.Sparks; ++I)
		{
			const double Ang = Rng.Uniform(0.0, kTwoPi);
			const double R = 2.0 * Cone * std::sqrt(Rng.Uniform01());
			const Vec3 Dir = (Bore + A1 * (R * std::cos(Ang)) + A2 * (R * std::sin(Ang))).Normalized();
			FCannonSpark S;
			S.P = Muzzle + Bore * 0.2;
			S.V = ShipV + Dir * (Params.SparkSpeedMs * Scale * Rng.Uniform(0.4, 1.0));
			S.Life = Params.SparkLifeS * Rng.Uniform(0.5, 1.0);
			SparkList.push_back(S);
		}
		// The muzzle's puffs glow with the flash at once.
		for (size_t I = PuffList.size() - size_t(N); I < PuffList.size(); ++I) PuffList[I].Glow = 1.0;
	}

	void FCannonSmoke::Step(double Dt, double Now, const ICannonWorld& World)
	{
		if (Dt <= 0.0) return;
		const FCannonParams& P = Params;
		// The flashes alive now (their light on the smoke).
		std::vector<std::pair<Vec3, double>> Lit;
		for (const FCannonFlash& F : FlashList)
		{
			const double I = F.Intensity(Now);
			if (I > 0.02 && !F.bPan) Lit.push_back({ F.P + F.Dir * (0.5 * F.LengthM), I });
		}
		const double GlowDecay = std::exp(-Dt / 0.06);
		const double HeatDecay = std::exp(-Dt / std::max(P.BuoyancyDecayS, 1e-3));
		for (FSmokePuff& S : PuffList)
		{
			S.Age += Dt;
			const Vec3 W = World.WindAt(S.P, Now);
			// The jet slows to the air fast (entrainment), then the slow puff rides the wind.
			const double B = Clamp(S.Age / 0.8, 0.0, 1.0);
			const double Tau = Lerp(std::max(P.JetDecayS, 1e-3), std::max(P.WindTakeS, 1e-3), B);
			const Vec3 Rel = S.V - W;
			const double RelSpeed = Rel.Length();
			S.V = W + Rel * std::exp(-Dt / Tau);
			S.V.Z += P.BuoyancyMs2 * S.Heat * Dt;
			S.Heat *= HeatDecay;
			S.P += S.V * Dt;
			// Growth: the jet's own spreading (about a tenth of the distance it runs through the air) and eddy diffusion.
			const double K = P.Diffusivity * std::pow(std::max(S.Sigma, 0.1), P.DiffusivityPower);
			S.Sigma = std::sqrt(S.Sigma * S.Sigma + 2.0 * K * Dt) + 0.1 * RelSpeed * Dt;
			// Each puff rides at its own height over the water (a shared multiple of sigma lined every puff's lower edge up
			// into one straight cut along the water: the second stills).
			const double Floor = World.WaterZ(S.P.X, S.P.Y, Now) + P.WaterLift * (0.6 + 0.8 * double(S.Seed)) * S.Sigma;
			if (S.P.Z < Floor) { S.P.Z = Floor; S.V.Z = std::max(S.V.Z, 0.0); }
			S.Glow *= GlowDecay;
			for (const auto& L : Lit)
			{
				const double D = (S.P - L.first).Length();
				if (D < P.FlashGlowM) S.Glow = std::max(S.Glow, L.second * (1.0 - D / P.FlashGlowM));
			}
		}
		// Gone: too faint or too old.
		PuffList.erase(std::remove_if(PuffList.begin(), PuffList.end(), [&](const FSmokePuff& S)
			{ return S.Age > P.SmokeMaxAgeS || (S.Age > 1.0 && S.Opacity(P) < P.MinPuffOpacity); }), PuffList.end());
		while (int32_t(PuffList.size()) > Budget) MergeOldest();

		FlashList.erase(std::remove_if(FlashList.begin(), FlashList.end(), [&](const FCannonFlash& F)
			{ return Now > F.Start + F.Life; }), FlashList.end());
		for (FCannonSpark& S : SparkList)
		{
			S.Age += Dt;
			const Vec3 W = World.WindAt(S.P, Now);
			S.V = W + (S.V - W) * std::exp(-Dt / 0.25);
			S.V.Z -= kG * Dt;
			S.P += S.V * Dt;
		}
		SparkList.erase(std::remove_if(SparkList.begin(), SparkList.end(), [](const FCannonSpark& S) { return S.Age > S.Life; }),
			SparkList.end());
	}

	void FCannonSmoke::MergeOldest()
	{
		if (PuffList.size() < 2) { PuffList.clear(); return; }
		size_t Old = 0;
		for (size_t I = 1; I < PuffList.size(); ++I)
		{
			if (PuffList[I].Age > PuffList[Old].Age) Old = I;
		}
		size_t Near = Old == 0 ? 1 : 0;
		double Best = 1e300;
		for (size_t I = 0; I < PuffList.size(); ++I)
		{
			if (I == Old) continue;
			const Vec3 Dd = PuffList[I].P - PuffList[Old].P;
			const double D = Dd.Dot(Dd);
			if (D < Best) { Best = D; Near = I; }
		}
		FSmokePuff& A = PuffList[Near];
		const FSmokePuff& B = PuffList[Old];
		const double M = std::max(A.MassKg + B.MassKg, 1e-9);
		const double WA = A.MassKg / M, WB = B.MassKg / M;
		const Vec3 C = A.P * WA + B.P * WB;
		// The merged blob keeps both one's spread and their separation (per axis: a third of the squared distance).
		const double S2 = WA * A.Sigma * A.Sigma + WB * B.Sigma * B.Sigma + WA * WB * Best / 3.0;
		A.V = A.V * WA + B.V * WB;
		A.P = C;
		A.Sigma = std::sqrt(S2);
		A.Age = A.Age * WA + B.Age * WB;
		A.Heat = A.Heat * WA + B.Heat * WB;
		A.Glow = std::max(A.Glow, B.Glow);
		A.MassKg = M;
		PuffList[Old] = PuffList.back();
		PuffList.pop_back();
		++MergeCount;
	}
}
